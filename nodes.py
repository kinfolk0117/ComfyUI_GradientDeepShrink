import torch

class GradientPatchModelAddDownscale:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": { "model": ("MODEL",),
                              "block_number": ("INT", {"default": 3, "min": 1, "max": 32, "step": 1}),
                              "downscale_factor": ("FLOAT", {"default": 2.0, "min": 0.1, "max": 9.0, "step": 0.001}),
                              "start_percent": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.001}),
                              "end_percent": ("FLOAT", {"default": 0.35, "min": 0.0, "max": 1.0, "step": 0.001}),
                              "downscale_after_skip": ("BOOLEAN", {"default": True}),
                              }}
    RETURN_TYPES = ("MODEL",)
    FUNCTION = "patch"

    CATEGORY = "_for_testing"

    def patch(self, model, block_number, downscale_factor, start_percent, end_percent, downscale_after_skip):
        sigma_start = model.model.model_sampling.percent_to_sigma(start_percent)
        sigma_end = model.model.model_sampling.percent_to_sigma(end_percent)

        # Linear scale factor between start_percent and end_percent, so 1/downscale_factor at start_percent and 1 at end_percent
        def calc_scale_factor(percent):
            if percent < start_percent:
                return 1.0 / downscale_factor
            elif percent > end_percent:
                return 1.0
            else:
                return 1.0 / downscale_factor + (1.0 - 1.0 / downscale_factor) * (percent - start_percent) / (end_percent - start_percent)

        # convert sigma to downscale factor
        def sigma_to_scale_factor(sigma):
            scale_factor = 1.0
            for i in range(0, 100):
                percent = i / 100.0
                s = model.model.model_sampling.percent_to_sigma(percent)
                if s > sigma:
                    scale_factor = calc_scale_factor(percent)
            return scale_factor
        
        def input_block_patch(h, transformer_options):
            if transformer_options["block"][1] == block_number:
                sigma = transformer_options["sigmas"][0].item()
                scale_factor = sigma_to_scale_factor(sigma)
                h = torch.nn.functional.interpolate(h, scale_factor=scale_factor, mode="bicubic", align_corners=False)
            return h

        def output_block_patch(h, hsp, transformer_options):
            if h.shape[2] != hsp.shape[2]:
                h = torch.nn.functional.interpolate(h, size=(hsp.shape[2], hsp.shape[3]), mode="bicubic", align_corners=False)
            return h, hsp

        m = model.clone()
        if downscale_after_skip:
            m.set_model_input_block_patch_after_skip(input_block_patch)
        else:
            m.set_model_input_block_patch(input_block_patch)
        m.set_model_output_block_patch(output_block_patch)
        return (m, )

class GradientPatchModelAddDownscaleAdvanced:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": { "model": ("MODEL",),
                              "block_number": ("INT", {"default": 3, "min": 1, "max": 32, "step": 1}),
                              "downscale_after_skip": ("BOOLEAN", {"default": True}),
                                "interpolate": ("BOOLEAN", {"default": True}),
                               "config": ("STRING", {"default": "0 0.5\n1 1", "multiline": True}),
                              }}
    RETURN_TYPES = ("MODEL",)
    FUNCTION = "patch"

    CATEGORY = "_for_testing"

    def patch(self, model, block_number, interpolate, config, downscale_after_skip):
        def parse_config(config_str):
            result = []
            for line in config_str.strip().split('\n'):
                percentage, scale_factor = map(float, line.split())
                result.append((percentage, scale_factor))
            return sorted(result)

        values = parse_config(config)
        for p, scale in values:
            print(p, scale)

        def interpolate_scale(percentage, lower, upper):
            lower_percentage, lower_scale = lower
            upper_percentage, upper_scale = upper

            if upper_percentage == lower_percentage:
                return lower_scale

            return lower_scale + (upper_scale - lower_scale) * ((percentage - lower_percentage) / (upper_percentage - lower_percentage))

        def scale_factor_from_percentage(percentage):
            lower = (0.0, 0.0)
            for p, scale in values:
                if percentage == p:
                    return scale
                elif percentage < p:
                    if interpolate and lower[0] != p:
                        return interpolate_scale(percentage, lower, (p, scale))
                    return lower[1]
                lower = (p, scale)
            return lower[1]

        # convert sigma to downscale factor
        def sigma_to_scale_factor(sigma):
            scale_factor = 1.0
            for i in range(0, 100):
                percent = i / 100.0
                s = model.model.model_sampling.percent_to_sigma(percent)
                if s > sigma:
                    scale_factor = scale_factor_from_percentage(percent)
            return scale_factor

        def input_block_patch(h, transformer_options):
            if transformer_options["block"][1] == block_number:
                sigma = transformer_options["sigmas"][0].item()
                scale_factor = sigma_to_scale_factor(sigma)
                h = torch.nn.functional.interpolate(h, scale_factor=scale_factor, mode="bicubic", align_corners=False)
            return h

        def output_block_patch(h, hsp, transformer_options):
            if h.shape[2] != hsp.shape[2]:
                h = torch.nn.functional.interpolate(h, size=(hsp.shape[2], hsp.shape[3]), mode="bicubic", align_corners=False)
            return h, hsp

        m = model.clone()
        if downscale_after_skip:
            m.set_model_input_block_patch_after_skip(input_block_patch)
        else:
            m.set_model_input_block_patch(input_block_patch)
        m.set_model_output_block_patch(output_block_patch)
        return (m, )


NODE_CLASS_MAPPINGS = {
    "GradientPatchModelAddDownscale": GradientPatchModelAddDownscale,
    "GradientPatchModelAddDownscaleAdvanced": GradientPatchModelAddDownscaleAdvanced,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    # Sampling
    "GradientPatchModelAddDownscale": "GradientPatchModelAddDownscale (Kohya Deep Shrink)",
    "GradientPatchModelAddDownscaleAdvanced": "GradientPatchModelAddDownscaleAdvanced (Kohya Deep Shrink)",
}
