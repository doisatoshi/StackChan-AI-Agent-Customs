# StackChan AI Inspector

**Active Perception with Local Gemma 4**

A Physical AI proof of concept that uses StackChan as a robot inspector and Gemma 4 as its local AI brain.

## Concept

**Simple, Slim, Compact + Smart**

Instead of combining multiple specialized AI models, this project uses a single Gemma 4 model for both visual localization and appearance inspection.

The key idea is not merely recognizing an object, but using visual understanding to control physical movement before inspecting it.

## System Architecture

- **Robot:** M5Stack StackChan / CoreS3
- **Local AI host:** MacBook Pro (Apple Silicon)
- **LLM / VLM:** Gemma 4 12B via Ollama
- **Communication:** xiaozhi-esp32-server and MCP
- **Speech synthesis:** VOICEVOX
- **Camera / motion:** StackChan camera and servo motors

Inference runs locally on the Mac. No cloud LLM is required for the inspection pipeline.

## Active Perception Workflow

1. The user asks StackChan to inspect the vehicle.
2. StackChan captures the first image.
3. Gemma 4 estimates the vehicle's position in the image.
4. Python converts the estimated horizontal position into a limited servo movement.
5. StackChan adjusts its camera direction.
6. StackChan captures another image.
7. Gemma 4 checks the vehicle type, body color, and roof color.
8. StackChan responds with the judgment and a Japanese spoken explanation.

The same VLM is reused with different prompts:

- **Position mode:** vehicle detection and approximate image position
- **Inspection mode:** visual observations, OK/NG judgment, and reason

## Inspection Criteria

A vehicle passes only when all three conditions are satisfied:

| Item | Required |
|---|---|
| Vehicle type | SUV |
| Body color | Orange |
| Roof color | White |

Scratches and dents are outside the current inspection scope.

## Demonstrated Results

| Test vehicle | Result |
|---|---|
| Orange SUV with white roof | OK |
| Black pickup truck | NG |

Both scenarios successfully completed the two-stage image capture, position-based MCP servo command, visual inspection, and Japanese speech response.

### Limitations

- Position adjustment is limited to one horizontal correction.
- Vehicle position is estimated using coarse image regions, not precise bounding boxes.
- The actual improvement in centering has not been quantitatively evaluated.
- Servo movement and inference latency depend on hardware and environment.
- This is a proof of concept, not a production-grade inspection system.

## Source Layout

- `firmware/`: modified StackChan firmware files
- `server/`: modified xiaozhi-server providers and MCP integration
- `config-examples/`: example local LLM/VLM/TTS configuration
- `licenses/`: original upstream license notices

These files are **customizations of upstream projects**, not a standalone firmware or server distribution. Apply them to compatible upstream source trees and build using the respective upstream instructions.

## Local AI Setup

1. Install and start Ollama on the host Mac.
2. Obtain the compatible `gemma4:12b` model.
3. Run the xiaozhi-server and configure the Ollama LLM provider.
4. Configure the OpenAI-compatible local VLM endpoint.
5. Start VOICEVOX and configure its TTS provider.
6. Integrate the supplied server customizations.
7. Integrate and build the supplied StackChan firmware customizations.
8. Configure the camera vision endpoint for the local server.
9. Test the voice-triggered inspection flow.

See `config-examples/config.yaml` for an illustrative configuration fragment. Adapt settings to your installed upstream version; do not use the example as a complete replacement configuration.

## Upstream Projects and Licenses

- [M5Stack StackChan](https://github.com/m5stack/StackChan) — MIT, Copyright (c) 2026 M5Stack Technology CO LTD
- [xiaozhi-esp32-server](https://github.com/xinnan-tech/xiaozhi-esp32-server) — MIT, Copyright (c) 2025 xinnan-tech

Original license notices are preserved in `licenses/`. Other runtime dependencies and models retain their respective license terms.

## Project Status

**Physical AI proof of concept: OK and NG inspection demonstrated on real hardware.**
