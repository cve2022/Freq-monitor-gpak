#!/usr/bin/env python3
"""Generate square-wave burst patterns from a JSON configuration file.

The generated text file contains two columns:
    time_us  level

The waveform structure matches the reference files used for the Go Configure
signal generator: each burst starts at level 0, contains an initial half-cycle
of low level, then N complete square-wave cycles, with a 0.1 us linear-edge
placeholder represented by two consecutive points. A silence interval is
inserted between the end of one burst and the start of the next.

Usage:
    python generate_wave_bursts.py config.json

The output filename is generated from the sweep parameters unless an explicit
output_file is supplied in the configuration.
"""

from __future__ import annotations

import argparse
import json
from decimal import Decimal, getcontext
from pathlib import Path

getcontext().prec = 40


def dec(value: object) -> Decimal:
    """Convert a JSON number/string to Decimal without binary-float artifacts."""
    return Decimal(str(value))


def fmt_number(value: Decimal) -> str:
    """Format a number for filenames, removing unnecessary trailing zeros."""
    s = format(value, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    if s == "-0":
        s = "0"
    return s


def inclusive_sweep(start: Decimal, end: Decimal, step: Decimal) -> list[Decimal]:
    """Return start..end inclusive, using Decimal arithmetic."""
    if step <= 0:
        raise ValueError("frequency step must be greater than zero")
    if end < start:
        raise ValueError("frequency end must be >= frequency start")

    values: list[Decimal] = []
    value = start
    # A Decimal comparison keeps this robust against floating-point drift.
    while value <= end:
        values.append(value)
        value += step

    # Catch configurations such as 0.1 steps that do not land exactly on end.
    if not values or values[-1] != end:
        raise ValueError(
            f"frequency sweep does not land exactly on end frequency: "
            f"start={start}, end={end}, step={step}"
        )
    return values


def build_filename(cfg: dict) -> str:
    prefix = str(cfg.get("filename_prefix", "go_configure"))
    sweep = cfg["frequency_sweep"]
    start = dec(sweep["start_khz"])
    end = dec(sweep["end_khz"])
    step = dec(sweep["step_khz"])
    burst = cfg["burst"]
    cycles = int(burst["cycles"])
    silence = dec(burst["silence_us"])

    # Keep the filename convention used by the reference files. The step is
    # deliberately not included because the established naming convention did
    # not include it either.
    return (
        f"{prefix}_{fmt_number(start)}_{fmt_number(end)}kHz_"
        f"{cycles}cycles_{fmt_number(silence)}us_silence.txt"
    )


def generate(cfg: dict, output_dir: Path) -> Path:
    sweep = cfg["frequency_sweep"]
    start_khz = dec(sweep["start_khz"])
    end_khz = dec(sweep["end_khz"])
    step_khz = dec(sweep["step_khz"])

    burst = cfg["burst"]
    cycles = int(burst["cycles"])
    silence_us = dec(burst["silence_us"])
    if cycles <= 0:
        raise ValueError("burst.cycles must be a positive integer")
    if silence_us < 0:
        raise ValueError("burst.silence_us must be >= 0")

    waveform = cfg["waveform"]
    low = dec(waveform.get("low", 0))
    high = dec(waveform["high"])
    edge_us = dec(waveform.get("edge_time_us", 0.1))
    if edge_us < 0:
        raise ValueError("waveform.edge_time_us must be >= 0")

    output = cfg.get("output", {})
    time_decimals = int(output.get("time_decimals", 3))
    if time_decimals < 0:
        raise ValueError("output.time_decimals must be >= 0")

    frequencies = inclusive_sweep(start_khz, end_khz, step_khz)
    points: list[tuple[Decimal, Decimal]] = []

    # Each burst explicitly starts with a low-level point. At a burst
    # boundary this intentionally duplicates the preceding boundary point,
    # matching the reference file format.
    burst_start_us = dec(cfg.get("start_time_us", 0))

    for burst_index, freq_khz in enumerate(frequencies):
        points.append((burst_start_us, low))
        period_us = Decimal("1000") / freq_khz
        half_period_us = period_us / Decimal("2")

        # N complete cycles. The first rising edge occurs after half a period,
        # matching the phase used by the reference files.
        for cycle in range(cycles):
            rise_us = burst_start_us + (Decimal(cycle) + Decimal("0.5")) * period_us
            fall_us = burst_start_us + Decimal(cycle + 1) * period_us

            # The source format uses a 0.1 us transition placeholder: the
            # signal remains at its old level until edge_us before the edge.
            points.append((rise_us - edge_us, low))
            points.append((rise_us, high))
            points.append((fall_us - edge_us, high))
            points.append((fall_us, low))
            # Preserve the duplicated low point between cycles, but not after
            # the final cycle of the burst.
            if cycle < cycles - 1:
                points.append((fall_us, low))

        # Silence begins exactly at the final falling edge. Add one explicit
        # boundary point; the next burst also adds its own start point, so the
        # two identical points at the boundary are intentional.
        if burst_index < len(frequencies) - 1:
            final_fall_us = burst_start_us + Decimal(cycles) * period_us
            burst_start_us = final_fall_us + silence_us
            points.append((burst_start_us, low))

    filename = output.get("output_file") or build_filename(cfg)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    fmt = f"{{:.{time_decimals}f}} {{:g}}\n"
    rendered = "".join(fmt.format(float(time_us), float(level)) for time_us, level in points)
    # The supplied reference files do not end with an extra blank line/newline.
    rendered = rendered.rstrip("\n")
    output_path.write_text(rendered, encoding="ascii", newline="\n")

    print(f"Generated: {output_path}")
    print(f"Frequencies: {start_khz:g} to {end_khz:g} kHz, step {step_khz:g} kHz ({len(frequencies)} values)")
    print(f"Cycles/burst: {cycles}; silence: {silence_us:g} us")
    print(f"Points: {len(points)}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate square-wave burst files from JSON configuration.")
    parser.add_argument("config", type=Path, help="JSON configuration file")
    parser.add_argument("-o", "--output-dir", type=Path, default=None,
                        help="Directory for generated output (default: config directory)")
    args = parser.parse_args()

    with args.config.open("r", encoding="utf-8") as fh:
        cfg = json.load(fh)

    output_dir = args.output_dir or args.config.parent
    generate(cfg, output_dir)


if __name__ == "__main__":
    main()
