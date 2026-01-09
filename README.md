# Icing's DryBox
Nade protocol test environment

-----

## What is it ?

The DryBox is a python CLI first, GUI assisted software that runs a communication simulation between two peers, “Left” and “Right”.
Think of it as a test bench with a device on each side.

Each peer can be any kind of software, while it is wrapped with a python “DryBox Adapter”, strictly following the DryBox Adapter ABI, defined in the (perhaps, slightly outdated) [documentation](https://github.com/Icing-Project/DryBox/blob/main/Spec_Adapter-interface_EN.md).
This adapter exposes simple but crucial functions the DryBox can hook on to push and pull data from the virtual device, expecting on its end some kind of treatment - or none.

The simulator runs on two different modes: Bytelink, and AudioBlock.

The Bytelink mode is made to abstract the “purely communication” layer from the Nade Protocol (keep in mind the DryBox has been created for Nade’s development), and thus expects and treats the adapters’ communication as simple, easy-to-use network-like data packets.
Its purpose is solely for core/protocol logic development and troubleshooting.

The audio block mode on the other hand, transmits C-contiguous int16 arrays from one side to the other, as a - currently - fixed and continuous mono 8 kHz, 16 bits depth audio stream.
This method is much closer to the real-world environment, and enables true FEC / Modem logic development.

## How to use it ?

The DryBox works both on Linux and Windows, but the Nade-Python package currently only supports Linux.

Feel free to tweak a custom Adapter and test it in the DryBox !

### Requirements

**[UV](https://docs.astral.sh/uv/getting-started/installation/)** (It is actually not mandatory, but recommended as easier to manage)
**[Python 3.10+](https://docs.astral.sh/uv/guides/install-python/)**

### Installation

Clone the repo

```bash
git clone https://github.com/Icing-Project/DryBox.git && cd DryBox
```

Install dependencies

```bash
uv sync
```

Run the DryBox (Gui mode)

```bash
uv run -m drybox.gui.app
```
or CLI mode

```bash
uv run drybox-run --help
```

### To install the Nade-Python package, which will be recognized as a DryBox Adapter

```bash
uv add --dev {Path to Nade-Python package}
```
