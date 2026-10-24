# Frequency monitor based on the GreenPAK SLG46826

## GoConfigure project files
The following files are configured, by default, to simulate the design:

- `freq-mon-sweep.gp6`: Project with a signal source configured to generate a frequency sweep, currently from 90 to 110 kHz in 1 kHz steps. Different patterns can be loaded (see below).
- `freq-mon.gp6`: Project with a signal source configured to generate a fixed-frequency square wave.

The same project files can also be used to program a GreenPAK SLG46826 (V variant, 20-STQFN package) by changing the development platform.

## Patterns
The `Python` folder contains a Python script that generates a text file from the pattern described in a JSON file. The contents of the generated text file can be copied and pasted into the signal source generator (Import tool).

Usage:

`python generate_wave_bursts.py pattern-description-file-name.json`

The generated `.txt` file contains the pattern in the `time voltage` format required by the signal source used for simulation. Time is expressed in us and voltage in mV.

The format of the .json files is self-explanatory.