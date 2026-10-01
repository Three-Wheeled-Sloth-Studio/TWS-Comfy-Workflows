import math


class AudioDurationToWanChunks:
    """Plan fixed-length Wan S2V chunks from a ComfyUI AUDIO value."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
                "fps": (
                    "FLOAT",
                    {"default": 16.0, "min": 1.0, "max": 120.0, "step": 0.01},
                ),
                "chunk_length": (
                    "INT",
                    {"default": 77, "min": 1, "max": 16384, "step": 4},
                ),
            }
        }

    RETURN_TYPES = ("FLOAT", "INT", "INT", "INT")
    RETURN_NAMES = (
        "duration_seconds",
        "target_frames",
        "total_chunks",
        "extension_iterations",
    )
    FUNCTION = "plan"
    CATEGORY = "audio/video planning"
    DESCRIPTION = (
        "Calculates how many fixed-length Wan S2V chunks are needed to cover "
        "the complete input audio."
    )

    def plan(self, audio, fps, chunk_length):
        waveform = audio.get("waveform")
        sample_rate = audio.get("sample_rate")
        if waveform is None or sample_rate is None:
            raise ValueError("The AUDIO input must contain waveform and sample_rate.")

        sample_count = int(waveform.shape[-1])
        sample_rate = int(sample_rate)
        if sample_rate <= 0:
            raise ValueError("Audio sample_rate must be greater than zero.")

        duration = sample_count / sample_rate
        target_frames = max(1, math.ceil(duration * float(fps)))
        total_chunks = max(1, math.ceil(target_frames / int(chunk_length)))

        # The loop's final value is produced by its body. Keeping at least one
        # extension also makes short-audio behavior deterministic; final frame
        # trimming still limits the result to the exact audio duration.
        extension_iterations = max(1, total_chunks - 1)
        total_chunks = extension_iterations + 1

        return (
            float(duration),
            int(target_frames),
            int(total_chunks),
            int(extension_iterations),
        )


NODE_CLASS_MAPPINGS = {
    "AudioDurationToWanChunks": AudioDurationToWanChunks,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AudioDurationToWanChunks": "Audio Duration to Wan S2V Chunks",
}


class WanS2VStateStart:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "initial_latent": ("LATENT",),
                "initial_positive": ("CONDITIONING",),
            },
        }

    RETURN_TYPES = ("WAN_S2V_STATE",)
    RETURN_NAMES = ("state",)
    FUNCTION = "create"
    CATEGORY = "audio/video planning"

    def create(self, initial_latent, initial_positive):
        samples = initial_latent["samples"].detach().to("cpu")
        ref_latent = None
        for conditioning_entry in initial_positive:
            metadata = conditioning_entry[1]
            reference_latents = metadata.get("reference_latents")
            if reference_latents:
                ref_latent = reference_latents[-1].detach().to("cpu")

        state = {
            "chunks": (samples,),
            "tail": samples[:, :, -19:],
            "frame_offset": int(samples.shape[-3]) * 4,
            "ref_latent": ref_latent,
        }
        return (state,)


class WanSoundImageToVideoExtendState:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "vae": ("VAE",),
                "length": ("INT", {"default": 77, "min": 1, "max": 16384, "step": 4}),
                "state": ("WAN_S2V_STATE",),
            },
            "optional": {
                "audio_encoder_output": ("AUDIO_ENCODER_OUTPUT",),
                "ref_image": ("IMAGE",),
                "control_video": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("CONDITIONING", "CONDITIONING", "LATENT")
    RETURN_NAMES = ("positive", "negative", "latent")
    FUNCTION = "extend"
    CATEGORY = "model/conditioning/wan/sound"

    def extend(
        self,
        positive,
        negative,
        vae,
        length,
        state,
        audio_encoder_output=None,
        ref_image=None,
        control_video=None,
    ):
        import node_helpers
        from comfy_extras.nodes_wan import wan_sound_to_video

        tail = state["tail"]
        width = int(tail.shape[-1]) * 8
        height = int(tail.shape[-2]) * 8
        batch_size = int(tail.shape[0])
        positive, negative, latent, _ = wan_sound_to_video(
            positive,
            negative,
            vae,
            width,
            height,
            length,
            batch_size,
            frame_offset=int(state["frame_offset"]),
            # The reference image is encoded once by WanS2VStateStart. Re-encoding
            # it here would swap the VAE and diffusion model on every iteration.
            ref_image=None,
            audio_encoder_output=audio_encoder_output,
            control_video=control_video,
            ref_motion=None,
            ref_motion_latent=tail,
        )
        ref_latent = state.get("ref_latent")
        if ref_latent is not None:
            positive = node_helpers.conditioning_set_values(
                positive, {"reference_latents": [ref_latent]}, append=True
            )
            negative = node_helpers.conditioning_set_values(
                negative, {"reference_latents": [ref_latent]}, append=True
            )
        return positive, negative, latent


class WanS2VStateAppend:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"state": ("WAN_S2V_STATE",), "chunk_latent": ("LATENT",)}}

    RETURN_TYPES = ("WAN_S2V_STATE",)
    RETURN_NAMES = ("state",)
    FUNCTION = "append"
    CATEGORY = "audio/video planning"

    def append(self, state, chunk_latent):
        chunk = chunk_latent["samples"].detach().to("cpu")
        next_state = {
            "chunks": state["chunks"] + (chunk,),
            "tail": chunk[:, :, -19:],
            "frame_offset": int(state["frame_offset"]) + int(chunk.shape[-3]) * 4,
            "ref_latent": state.get("ref_latent"),
        }
        # Long dynamic loops otherwise retain increasingly fragmented CUDA
        # allocator blocks between sampler invocations.
        try:
            import comfy.model_management

            comfy.model_management.soft_empty_cache()
        except ImportError:
            pass
        return (next_state,)


class WanS2VStateToLatent:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"state": ("WAN_S2V_STATE",)}}

    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("latent",)
    FUNCTION = "combine"
    CATEGORY = "audio/video planning"

    def combine(self, state):
        import torch

        return ({"samples": torch.cat(state["chunks"], dim=-3)},)


NODE_CLASS_MAPPINGS.update(
    {
        "WanS2VStateStart": WanS2VStateStart,
        "WanSoundImageToVideoExtendState": WanSoundImageToVideoExtendState,
        "WanS2VStateAppend": WanS2VStateAppend,
        "WanS2VStateToLatent": WanS2VStateToLatent,
    }
)

NODE_DISPLAY_NAME_MAPPINGS.update(
    {
        "WanS2VStateStart": "Wan S2V Start CPU State",
        "WanSoundImageToVideoExtendState": "Wan S2V Extend from CPU State",
        "WanS2VStateAppend": "Wan S2V Append Chunk to CPU State",
        "WanS2VStateToLatent": "Wan S2V Combine CPU Chunks",
    }
)
