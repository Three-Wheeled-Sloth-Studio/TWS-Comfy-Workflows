# Agent entry point

This repository is embedded in a live ComfyUI data directory. Before editing:

1. Run `python refs/tools/generate_agent_context.py --focus "<task>"`.
2. Read the required files named by that packet.
3. Treat `.gitignore` as a security boundary. Never broaden it to include model files, media, outputs, caches, secrets, or general `user/` configuration.
4. Only `custom_nodes/comfyui_audio_duration_plan/` is project-owned. Other `custom_nodes/` entries are third-party installations.
5. Update `refs/handoffs/currentHandoff.md` and relevant planning evidence when findings or implementation state materially change.
6. Run the commands in `refs/testing/validationCommands.yaml` before finishing.

Do not stop or restart ComfyUI, alter active queues, download large models, or push external changes unless the user request includes that action.
