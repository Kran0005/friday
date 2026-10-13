import os


def get_input_device_index(audio):
    """Return the default or best physical microphone input visible to PyAudio."""
    configured = os.getenv("FRIDAY_MIC_DEVICE", "").strip()
    devices = [audio.get_device_info_by_index(i) for i in range(audio.get_device_count())]
    inputs = [device for device in devices if device["maxInputChannels"] > 0]

    if configured:
        if configured.isdecimal():
            index = int(configured)
            device = audio.get_device_info_by_index(index)
            if device["maxInputChannels"] <= 0:
                raise RuntimeError(f"FRIDAY_MIC_DEVICE={index} is not an input device.")
            return index

        matches = [device for device in inputs if configured.casefold() in device["name"].casefold()]
        if not matches:
            raise RuntimeError(f"No microphone matches FRIDAY_MIC_DEVICE={configured!r}.")
        return int(matches[0]["index"])

    try:
        default_index = int(audio.get_default_input_device_info()["index"])
        if audio.get_device_info_by_index(default_index)["maxInputChannels"] > 0:
            return default_index
    except (OSError, IOError):
        pass

    physical_mics = [
        device for device in inputs
        if "microphone" in device["name"].casefold()
        and "stereo mix" not in device["name"].casefold()
    ]
    if physical_mics:
        return int(physical_mics[0]["index"])

    if inputs:
        names = ", ".join(device["name"] for device in inputs)
        raise RuntimeError(
            "No default microphone is selected and no device named Microphone was found. "
            f"Available input devices: {names}. Set FRIDAY_MIC_DEVICE to a device name or index."
        )
    raise RuntimeError("Windows reports no microphone input devices. Connect or enable a microphone.")
