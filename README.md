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

## Important Notes

**PCB Setup Requirements:**
When exporting your position file, ensure that:
- Grid origin is positioned at the bottom-left corner of the PCB's bounding rectangle
- Drill holes reference the same bottom-left origin point

This coordinate system alignment is critical for accurate component placement in the rendered output.

**Component Customization:**
After running the tool, a `component_config.json` file will be generated in your Gerber folder. You can edit this file to fine-tune:
- Component rotation angles
- Scaling factors for individual components
- SVG file mappings for specific components

The tool automatically attempts to match components to SVGs, but manual adjustments may be needed for optimal visual results.

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
