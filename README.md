# Forge - PCB Renderer with Component Placement

A command-line tool for rendering PCBs from Gerber files with component placement visualization.

## Installation

Install directly from GitHub:

```bash
pip install git+https://github.com/yourusername/Forge_cli.git
```

## Usage

```bash
forge --files ./gerber_folder --components ./component_svgs
```

### Options

- `--files`, `-f`: Path to folder containing Gerber files (.svg format)
- `--components`, `-c`: Path to folder containing component SVG files
- `--config-only`: Generate component configuration without rendering
- `--colors`: Customize colors (background, PCB, silkscreen, pads)

### Example

```bash
# Basic usage
forge -f ./my_pcb_gerbers -c ./component_library

# Custom colors
forge -f ./gerbers -c ./components --colors '#1a1a1a' '#2d5a3d' '#ffffff' '#ffd700'

# Generate config only
forge -f ./gerbers -c ./components --config-only
```

## Requirements

- Python 3.8+
- lxml library (installed automatically)

## Input Files

The tool expects:
- Gerber files in SVG format in the `--files` directory
- Component position CSV file (*-pos.csv)
- Component SVG files in the `--components` directory

## Output

Creates rendered PCB visualizations in an `output/` folder:
- Top view with components
- Bottom view with components  
- Combined side-by-side view

## Development

Clone and install in development mode:

```bash
git clone https://github.com/yourusername/Forge_cli.git
cd Forge_cli
pip install -e .
```
