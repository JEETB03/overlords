import base64
import binascii
import logging
import time
import uuid
from typing import Dict, Any, Optional, List, Tuple
from app.config import settings

logger = logging.getLogger("overlord.lora")

class LoRaPacket:
    def __init__(
        self,
        transmission_id: str,
        packet_num: int,
        total_packets: int,
        payload_b64: str,
        rssi: float = -82.0,
        snr: float = 9.2,
        crc: Optional[str] = None
    ):
        self.transmission_id = transmission_id
        self.packet_num = packet_num
        self.total_packets = total_packets
        self.payload_b64 = payload_b64
        self.rssi = rssi
        self.snr = snr
        self.crc = crc
        self.timestamp = time.time()

class LoRaReassemblySession:
    def __init__(self, transmission_id: str, total_packets: int):
        self.transmission_id = transmission_id
        self.total_packets = total_packets
        self.chunks: Dict[int, bytes] = {}
        self.started_at = time.time()
        self.last_packet_time = time.time()
        self.rssi_values: List[float] = []
        self.snr_values: List[float] = []
        self.metadata: Dict[str, Any] = {}

    def add_packet(self, packet_num: int, payload_bytes: bytes, rssi: float, snr: float):
        self.chunks[packet_num] = payload_bytes
        self.last_packet_time = time.time()
        self.rssi_values.append(rssi)
        self.snr_values.append(snr)

    @property
    def progress_pct(self) -> float:
        return (len(self.chunks) / max(self.total_packets, 1)) * 100.0

    @property
    def is_complete(self) -> bool:
        return len(self.chunks) >= self.total_packets

    @property
    def avg_rssi(self) -> float:
        return sum(self.rssi_values) / max(len(self.rssi_values), 1)

    @property
    def avg_snr(self) -> float:
        return sum(self.snr_values) / max(len(self.snr_values), 1)

    def assemble(self) -> bytes:
        data = bytearray()
        for i in range(1, self.total_packets + 1):
            if i in self.chunks:
                data.extend(self.chunks[i])
        return bytes(data)

class LoRaService:
    def __init__(self):
        self.sessions: Dict[str, LoRaReassemblySession] = {}
        self.total_packets_received = 0
        self.last_rssi = -72.0
        self.last_snr = 9.5
        self.hardware_active = False

    def fragment_payload(
        self,
        raw_bytes: bytes,
        chunk_size: int = 128
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Fragments a binary payload into simulated LoRa packets."""
        tx_id = str(uuid.uuid4())[:8]
        total_chunks = (len(raw_bytes) + chunk_size - 1) // chunk_size
        packets = []

        for idx in range(total_chunks):
            chunk = raw_bytes[idx * chunk_size : (idx + 1) * chunk_size]
            crc = f"{binascii.crc32(chunk):08x}"
            b64 = base64.b64encode(chunk).decode("ascii")
            packets.append({
                "transmission_id": tx_id,
                "packet_num": idx + 1,
                "total_packets": total_chunks,
                "payload_b64": b64,
                "crc": crc,
                "rssi": round(-70.0 - (idx % 15) * 1.5, 1),
                "snr": round(10.0 - (idx % 6) * 0.4, 1),
                "freq_mhz": settings.LORA_FREQUENCY_MHZ,
                "sf": settings.LORA_SPREADING_FACTOR
            })

        return tx_id, packets

    def ingest_packet(
        self,
        transmission_id: str,
        packet_num: int,
        total_packets: int,
        payload_b64: str,
        rssi: float = -80.0,
        snr: float = 8.5,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Processes an incoming LoRa packet chunk."""
        self.total_packets_received += 1
        self.last_rssi = rssi
        self.last_snr = snr

        if transmission_id not in self.sessions:
            self.sessions[transmission_id] = LoRaReassemblySession(
                transmission_id=transmission_id,
                total_packets=total_packets
            )
            if metadata:
                self.sessions[transmission_id].metadata = metadata

        session = self.sessions[transmission_id]
        payload_bytes = base64.b64decode(payload_b64)
        session.add_packet(packet_num, payload_bytes, rssi, snr)

        result = {
            "transmission_id": transmission_id,
            "packet_num": packet_num,
            "total_packets": total_packets,
            "progress_pct": round(session.progress_pct, 1),
            "is_complete": session.is_complete,
            "avg_rssi": round(session.avg_rssi, 1),
            "avg_snr": round(session.avg_snr, 1),
            "reconstructed_bytes": None,
            "metadata": session.metadata
        }

        if session.is_complete:
            result["reconstructed_bytes"] = session.assemble()
            logger.info(f"LoRa transmission {transmission_id} complete ({len(result['reconstructed_bytes'])} bytes)")

        return result

    def get_status(self) -> Dict[str, Any]:
        return {
            "enabled": settings.LORA_ENABLED,
            "frequency_mhz": settings.LORA_FREQUENCY_MHZ,
            "bandwidth_khz": settings.LORA_BANDWIDTH_KHZ,
            "spreading_factor": settings.LORA_SPREADING_FACTOR,
            "coding_rate": settings.LORA_CODING_RATE,
            "total_packets_received": self.total_packets_received,
            "last_rssi": self.last_rssi,
            "last_snr": self.last_snr,
            "active_sessions": len(self.sessions),
            "hardware_port": settings.LORA_SERIAL_PORT,
            "mode": "HARDWARE" if self.hardware_active else "BRIDGE/SIMULATION"
        }

lora_service = LoRaService()
