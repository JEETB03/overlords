import base64
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.models import LoRaPacketIn
from app.config import settings
from app.services.lora_service import lora_service
from app.services.simulator import simulator

router = APIRouter(prefix="/lora", tags=["lora"])

class RawLoRaPacket(BaseModel):
    transmission_id: str
    packet_num: int
    total_packets: int
    payload_b64: str
    rssi: float = -80.0
    snr: float = 8.5
    metadata: Optional[Dict[str, Any]] = None

@router.get("/status")
async def get_lora_status():
    """Returns status and radio metrics of the LoRa gateway."""
    return lora_service.get_status()

@router.post("/rx")
async def receive_lora_packet(packet: RawLoRaPacket):
    """
    Ingest endpoint for LoRa packet chunks from physical hardware
    (e.g., SX1262/SX1276 serial bridge, Heltec ESP32, or Meshtastic node).
    """
    result = lora_service.ingest_packet(
        transmission_id=packet.transmission_id,
        packet_num=packet.packet_num,
        total_packets=packet.total_packets,
        payload_b64=packet.payload_b64,
        rssi=packet.rssi,
        snr=packet.snr,
        metadata=packet.metadata
    )

    if result.get("is_complete"):
        await simulator.emit_alert(
            severity="INFO",
            title="LORA IMAGE PACKET REASSEMBLY COMPLETE",
            message=f"LoRa Session {packet.transmission_id}: Reconstructed {packet.total_packets}/{packet.total_packets} chunks via {settings.LORA_FREQUENCY_MHZ}MHz.",
            drone_id="LORA-GW",
            data={"transmission_id": packet.transmission_id}
        )

    return result

@router.post("/test-burst")
async def simulate_lora_test_burst():
    """Generates a test LoRa packet burst."""
    dummy_payload = b"OVERLORD_LORA_BEACON_TEST_PACKET_CHECKSUM_OK" * 4
    tx_id, packets = lora_service.fragment_payload(dummy_payload, chunk_size=32)
    for p in packets:
        lora_service.ingest_packet(
            transmission_id=p["transmission_id"],
            packet_num=p["packet_num"],
            total_packets=p["total_packets"],
            payload_b64=p["payload_b64"],
            rssi=p["rssi"],
            snr=p["snr"]
        )
    return {
        "status": "SENT",
        "transmission_id": tx_id,
        "packets_sent": len(packets)
    }
