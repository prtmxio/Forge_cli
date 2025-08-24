#!/usr/bin/env python3
import argparse
import sys
import re
import base64
import json
from pathlib import Path
import csv
try:
    from lxml import etree as ET
except ImportError:
    print("ERROR: This script requires the 'lxml' library.")
    print("Please install it by running: pip install lxml")
    sys.exit(1)


class ComponentPlacer:
    def __init__(self, component_folder, gerber_folder):
        self.component_folder = Path(component_folder)
        self.component_folder.mkdir(exist_ok=True)
        self.available_svgs = self._discover_available_svgs()
        self.config_path = Path(gerber_folder) / "component_config.json"
        self.config = self._load_or_create_config()
        self.auto_mapping_rules = self._create_auto_mapping_rules()

    def _discover_available_svgs(self):
        svg_files = {}
        for svg_file in self.component_folder.glob("*.svg"):
            key = svg_file.stem
            svg_files[key] = svg_file
        return svg_files

    def _create_auto_mapping_rules(self):
        return {
            'ref_patterns': {
                'R': ['Resistor', 'resistor', 'RES'],
                'C': ['Capacitor', 'capacitor', 'CAP'],
                'D': ['Diode', 'diode', 'LED'],
                'Q': ['Si2301', 'Transistor', 'transistor', 'SOT-23'],
                'U': ['IC', '8 PIN IC', 'IC-Module', 'chip'],
                'J': ['CONN', 'connector', 'JST', 'USB'],
                'SW': ['Button', 'Switch', 'SW-SPDT', 'SW-SPST'],
                'Y': ['Crystal', 'crystal', 'OSC'],
            },
            'package_patterns': {
                'SOT-23': ['Si2301', 'SOT-23', 'transistor'],
                'SOT-23-5': ['AP211K', 'AP2112', 'SOT-23-5'],
                'C_0603': ['Capacitor', 'capacitor'],
                'R_0603': ['Resistor', 'resistor'],
                'LED_0603': ['LED', 'led'],
                'D_SMA': ['Diode', 'diode'],
                'USB_C': ['USB', 'usb'],
                'ESP32': ['IC-Module', 'ESP32'],
                'JST_SH': ['CONN', 'JST'],
                'PinSocket': ['CONN', 'connector'],
                'SW_SPST': ['Button', 'button'],
                'SW_SPDT': ['SW-SPDT', 'switch'],
            },
            'value_patterns': {
                'led': ['LED', 'led'],
                'esp32': ['IC-Module', 'ESP32'],
                'usb': ['USB', 'usb'],
                'crystal': ['Crystal', 'crystal'],
            }
        }

    def _load_or_create_config(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                return config
            except Exception as e:
                print(f"❌ Error loading config: {e}")
                return {}
        else:
            return {}

    def _find_best_svg_match(self, search_terms):
        for term in search_terms:
            for svg_key in self.available_svgs.keys():
                if term.lower() == svg_key.lower():
                    return svg_key
            for svg_key in self.available_svgs.keys():
                if term.lower() in svg_key.lower() or svg_key.lower() in term.lower():
                    return svg_key
        return None

    def _auto_assign_svg(self, component):
        ref = component['reference']
        package = component.get('package', '').lower()
        value = component['value'].lower()
        search_terms = []
        prefix = ref[0] if ref else ''
        if prefix in self.auto_mapping_rules['ref_patterns']:
            search_terms.extend(self.auto_mapping_rules['ref_patterns'][prefix])
        for pattern, terms in self.auto_mapping_rules['package_patterns'].items():
            if pattern.lower() in package:
                search_terms.extend(terms)
                break
        for pattern, terms in self.auto_mapping_rules['value_patterns'].items():
            if pattern in value:
                search_terms.extend(terms)
                break
        if ref.startswith('D') and 'led' in value:
            search_terms = ['LED', 'led'] + search_terms
        elif 'esp32' in value or 'esp32' in package:
            search_terms = ['IC-Module', 'ESP32'] + search_terms
        elif 'usb' in package or 'usb' in value:
            search_terms = ['USB', 'usb'] + search_terms
        svg_match = self._find_best_svg_match(search_terms)
        if svg_match:
            return svg_match
        else:
            return None

    def generate_universal_config(self, components):
        config_updated = False
        if 'global_mappings' not in self.config:
            self.config['global_mappings'] = {
                "available_svgs": list(self.available_svgs.keys()),
                "by_reference_prefix": {},
                "by_package": {},
                "by_value_keyword": {}
            }
            config_updated = True
        for comp in components:
            ref = comp['reference']
            if ref not in self.config:
                self.config[ref] = {
                    "svg": None,
                    "rotation": comp['rotation'],
                    "scale": 0.056,
                    "package": comp.get('package', ''),
                    "value": comp['value']
                }
                config_updated = True
            if not self.config[ref].get('svg'):
                svg_match = self._auto_assign_svg(comp)
                if svg_match:
                    self.config[ref]['svg'] = svg_match
                    config_updated = True
            self.config[ref]['package'] = comp.get('package', '')
            self.config[ref]['value'] = comp['value']
        self._update_global_mappings()
        if config_updated:
            self._save_config()
        return self.config

    def _update_global_mappings(self):
        self.config['global_mappings']['available_svgs'] = list(self.available_svgs.keys())
        ref_mappings = {}
        package_mappings = {}
        value_mappings = {}
        for ref, comp_config in self.config.items():
            if ref == 'global_mappings':
                continue
            svg = comp_config.get('svg')
            if not svg:
                continue
            prefix = ref[0] if ref else ''
            if prefix and prefix not in ref_mappings:
                ref_mappings[prefix] = svg
            package = comp_config.get('package', '')
            if package and package not in package_mappings:
                package_mappings[package] = svg
            value = comp_config.get('value', '').lower()
            for keyword in ['led', 'usb', 'esp32', 'crystal']:
                if keyword in value and keyword not in value_mappings:
                    value_mappings[keyword] = svg
        self.config['global_mappings']['by_reference_prefix'].update(ref_mappings)
        self.config['global_mappings']['by_package'].update(package_mappings)
        self.config['global_mappings']['by_value_keyword'].update(value_mappings)

    def _save_config(self):
        try:
            sorted_config = {}
            if 'global_mappings' in self.config:
                sorted_config['global_mappings'] = self.config['global_mappings']
            component_refs = [k for k in self.config.keys() if k != 'global_mappings']
            component_refs.sort()
            for ref in component_refs:
                sorted_config[ref] = self.config[ref]
            with open(self.config_path, 'w') as f:
                json.dump(sorted_config, f, indent=2, sort_keys=False)
        except Exception as e:
            print(f"❌ Failed to save config: {e}")

    def load_csv_file(self, csv_file_path):
        components = []
        csv_path = Path(csv_file_path)
        if not csv_path.exists():
            print(f"Warning: CSV file not found at {csv_file_path}")
            return components
        try:
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        component = {
                            'reference': row['Ref'].strip('"'),
                            'value': row['Val'].strip('"'),
                            'package': row['Package'].strip('"'),
                            'x': float(row['PosX']),
                            'y': float(row['PosY']),
                            'rotation': float(row['Rot']),
                            'side': row['Side'].strip('"').lower()
                        }
                        components.append(component)
                    except (ValueError, KeyError) as e:
                        print(f"❌ Error parsing CSV row: {row} - {e}")
                        continue
        except Exception as e:
            print(f"❌ Error reading CSV file: {e}")
            return components
        self.generate_universal_config(components)
        # self._print_mapping_summary() # Removed for cleaner output
        return components

    def find_component_svg(self, component):
        ref = component['reference']
        if ref in self.config and self.config[ref].get('svg'):
            svg_name = self.config[ref]['svg']
            svg_path = self.available_svgs.get(svg_name)
            if svg_path and svg_path.exists():
                return svg_path
            else:
                print(f"⚠️  SVG file not found: {svg_name}.svg for {ref}")
        svg_name = self._auto_assign_svg(component)
        if svg_name and svg_name in self.available_svgs:
            return self.available_svgs[svg_name]
        return None

    def calculate_component_scale(self, component, pcb_bounds):
        ref = component['reference']
        if ref in self.config and 'scale' in self.config[ref]:
            return self.config[ref]['scale']
        return 1.0

    def get_component_rotation(self, component):
        ref = component['reference']
        if ref in self.config and 'rotation' in self.config[ref]:
            return self.config[ref]['rotation']
        return component['rotation']

    def _print_mapping_summary(self):
        mapped = 0
        unmapped = []
        for ref, comp_config in self.config.items():
            if ref == 'global_mappings':
                continue
            if comp_config.get('svg'):
                mapped += 1
            else:
                unmapped.append(ref)
        total = len([k for k in self.config.keys() if k != 'global_mappings'])
        print(f"\n📊 Component Mapping Summary:")
        print(f"   Available SVG files: {len(self.available_svgs)}")
        print(f"   Total components: {total}")
        print(f"   Mapped components: {mapped}")
        print(f"   Unmapped components: {len(unmapped)}")
        if unmapped:
            print(f"\n❌ Unmapped components: {', '.join(unmapped[:5])}")
            if len(unmapped) > 5:
                print(f"   ... and {len(unmapped) - 5} more")

    def parse_svg(self, filepath):
        try:
            return ET.parse(filepath).getroot()
        except Exception as e:
            print(f"Error parsing {filepath}: {e}")
            return None

    def get_component_bounds(self, svg_root):
        viewBox = svg_root.get('viewBox')
        if viewBox:
            try:
                vb = [float(x) for x in viewBox.split()]
                min_x_vb, min_y_vb, width_vb, height_vb = vb
                center_x = min_x_vb + width_vb / 2
                center_y = min_y_vb + height_vb / 2
                return center_x, center_y, width_vb, height_vb
            except:
                pass
        min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
        def process_element(element):
            nonlocal min_x, min_y, max_x, max_y
            tag = element.tag.split('}')[-1]
            if tag == 'rect':
                x, y = float(element.get('x', 0)), float(element.get('y', 0))
                w, h = float(element.get('width', 0)), float(element.get('height', 0))
                min_x, max_x = min(min_x, x), max(max_x, x + w)
                min_y, max_y = min(min_y, y), max(max_y, y + h)
            elif tag == 'circle':
                cx, cy, r = float(element.get('cx', 0)), float(element.get('cy', 0)), float(element.get('r', 0))
                min_x, max_x = min(min_x, cx - r), max(max_x, cx + r)
                min_y, max_y = min(min_y, cy - r), max(max_y, cy + r)
            elif tag == 'path':
                coords = [float(c) for c in re.findall(r'-?\d+\.?\d*(?:[eE][-+]?\d+)?', element.get('d', ''))]
                for i in range(0, len(coords), 2):
                    if i + 1 < len(coords):
                        min_x, max_x = min(min_x, coords[i]), max(max_x, coords[i])
                        min_y, max_y = min(min_y, coords[i + 1]), max(max_y, coords[i + 1])
            for child in element:
                process_element(child)
        process_element(svg_root)
        if min_x == float('inf'):
            return 0, 0, 10, 10
        width = max_x - min_x
        height = max_y - min_y
        center_x = min_x + width / 2
        center_y = min_y + height / 2
        return center_x, center_y, width, height


class SVGProcessor:
    def __init__(self):
        pass

    def parse_svg(self, filepath):
        try:
            return ET.parse(filepath).getroot()
        except Exception as e:
            print(f"Error parsing {filepath}: {e}")
            return None

    def _get_drawable_elements(self, element):
        drawable = []
        ns = '{http://www.w3.org/2000/svg}'
        tag_name = element.tag[len(ns):] if element.tag.startswith(ns) else element.tag
        if tag_name in ['path', 'circle', 'rect', 'line', 'polygon', 'polyline', 'ellipse']:
            drawable.append(element)
        for child in element:
            drawable.extend(self._get_drawable_elements(child))
        return drawable

    def _calculate_bounds(self, root):
        min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
        shapes = self._get_drawable_elements(root)
        ns = '{http://www.w3.org/2000/svg}'
        for shape in shapes:
            if shape.tag in [f'{ns}circle', 'circle']:
                cx, cy, r = float(shape.get('cx', 0)), float(shape.get('cy', 0)), float(shape.get('r', 0))
                min_x, max_x = min(min_x, cx - r), max(max_x, cx + r)
                min_y, max_y = min(min_y, cy - r), max(max_y, cy + r)
            elif shape.tag in [f'{ns}path', 'path']:
                coords = [float(c) for c in re.findall(r'-?\d+\.?\d*(?:[eE][-+]?\d+)?', shape.get('d', ''))]
                if len(coords) % 2 == 0:
                    for i in range(0, len(coords), 2):
                        if i + 1 < len(coords):
                            min_x, max_x = min(min_x, coords[i]), max(max_x, coords[i])
                            min_y, max_y = min(min_y, coords[i+1]), max(max_y, coords[i+1])
            elif shape.tag in [f'{ns}rect', 'rect']:
                x, y = float(shape.get('x', 0)), float(shape.get('y', 0))
                w, h = float(shape.get('width', 0)), float(shape.get('height', 0))
                min_x, max_x = min(min_x, x), max(max_x, x + w)
                min_y, max_y = min(min_y, y), max(max_y, y + h)
        if min_x == float('inf'):
            return 0, 0, 100, 100
        return min_x, min_y, max_x - min_x, max_y - min_y

    def _create_clean_copy(self, element):
        clean_copy = ET.Element(element.tag, dict(element.attrib))
        for attr in ['fill', 'stroke', 'style', 'stroke-width']:
            if attr in clean_copy.attrib:
                del clean_copy.attrib[attr]
        clean_copy.text = element.text
        clean_copy.tail = element.tail
        return clean_copy

    def _is_mounting_hole(self, element, pcb_bounds):
        ns = '{http://www.w3.org/2000/svg}'
        if element.tag in [f'{ns}circle', 'circle']:
            r = float(element.get('r', 0))
            cx = float(element.get('cx', 0))
            cy = float(element.get('cy', 0))
            x_min, y_min, width, height = pcb_bounds
            x_max = x_min + width
            y_max = y_min + height
            near_left = cx < (x_min + width * 0.25)
            near_right = cx > (x_max - width * 0.25)
            near_top = cy < (y_min + height * 0.25)
            near_bottom = cy > (y_max - height * 0.25)
            is_large = r > 1.0
            is_corner = (near_left or near_right) and (near_top or near_bottom)
            return is_large and is_corner
        return False
    
    
    def _has_inner_circle_nearby(self, element, all_circles, tolerance=0.5):
        ns = '{http://www.w3.org/2000/svg}'
        if element.tag not in [f'{ns}circle', 'circle']:
            return False
        cx = float(element.get('cx', 0))
        cy = float(element.get('cy', 0))
        r = float(element.get('r', 0))
        for other in all_circles:
            if other == element:
                continue
            other_cx = float(other.get('cx', 0))
            other_cy = float(other.get('cy', 0))
            other_r = float(other.get('r', 0))
            distance = ((cx - other_cx) ** 2 + (cy - other_cy) ** 2) ** 0.5
            if distance <= tolerance and other_r < r:
                return True
        return False

    def _is_near_corner(self, element, pcb_bounds):
        ns = '{http://www.w3.org/2000/svg}'
        x_min, y_min, width, height = pcb_bounds
        if element.tag in [f'{ns}circle', 'circle']:
            cx = float(element.get('cx', 0))
            cy = float(element.get('cy', 0))
            r = float(element.get('r', 0))
            if r < 2.0:
                return False
        elif element.tag in [f'{ns}rect', 'rect']:
            x = float(element.get('x', 0))
            y = float(element.get('y', 0))
            w = float(element.get('width', 0))
            h = float(element.get('height', 0))
            cx = x + w / 2
            cy = y + h / 2
        elif element.tag in [f'{ns}path', 'path']:
            bbox = self._get_path_bbox(element)
            if not bbox:
                return False
            x, y, w, h = bbox
            cx = x + w / 2
            cy = y + h / 2
        else:
            return False
        corner_threshold = 0.2
        near_left = cx < (x_min + width * corner_threshold)
        near_right = cx > (x_min + width * (1 - corner_threshold))
        near_top = cy < (y_min + height * corner_threshold)
        near_bottom = cy > (y_min + height * (1 - corner_threshold))
        return (near_left or near_right) and (near_top or near_bottom)

    def _get_path_bbox(self, path_element):
        d_attr = path_element.get('d', '')
        coords = [float(c) for c in re.findall(r'-?\d+\.?\d*(?:[eE][-+]?\d+)?', d_attr)]
        if len(coords) < 2:
            return None
        points_x = coords[0::2]
        points_y = coords[1::2]
        if not points_x or not points_y:
            return None
        min_x, max_x = min(points_x), max(points_x)
        min_y, max_y = min(points_y), max(points_y)
        return min_x, min_y, max_x - min_x, max_y - min_y

    def _create_pcb_base(self, output_svg, edgecut_root, pcb_bounds, colors, transparent_bg=False):
        bg_color, pcb_color, silk_color, pad_color = colors
        x, y, width, height = pcb_bounds
        padding = 5.0
        # Background rectangle
        ET.SubElement(output_svg, 'rect', {
            'x': str(x - padding),
            'y': str(y - padding),
            'width': str(width + padding*2),
            'height': str(height + padding*2),
            'fill': bg_color
        })
        # Extract corner radius
        all_paths = edgecut_root.findall('.//{*}path')
        arc_path_d = next((path.get('d', '') for path in all_paths if 'A' in path.get('d', '')), None)
        radius = 3.0
        if arc_path_d:
            radius_match = re.search(r'A\s*(\d+\.?\d*)', arc_path_d)
            if radius_match:
                radius = float(radius_match.group(1))
        w, h, r = width, height, radius
        path_data = (f"M {x+r},{y} L {x+w-r},{y} A {r},{r} 0 0 1 {x+w},{y+r} L {x+w},{y+h-r} "
                    f"A {r},{r} 0 0 1 {x+w-r},{y+h} L {x+r},{y+h} A {r},{r} 0 0 1 {x},{y+h-r} "
                    f"L {x},{y+r} A {r},{r} 0 0 1 {x+r},{y} Z")
        ET.SubElement(output_svg, 'path', {'d': path_data, 'fill': pcb_color})
        # Handle mounting holes
        all_circles = edgecut_root.findall('.//{*}circle')
        mounting_holes = [circle for circle in all_circles if self._is_mounting_hole(circle, pcb_bounds)]
        if mounting_holes:
            hole_punch_group = ET.SubElement(output_svg, 'g', {
                'fill': bg_color,
                'stroke': 'none'
            })
            for hole in mounting_holes:
                hole_punch_group.append(ET.Element(hole.tag, dict(hole.attrib)))
        return path_data, mounting_holes

    def _is_overlap(self, rect1, rect2, tolerance=0.1):
        return (rect1['x'] < rect2['x'] + rect2['w'] - tolerance and
                rect1['x'] + rect1['w'] > rect2['x'] + tolerance and
                rect1['y'] < rect2['y'] + rect2['h'] - tolerance and
                rect1['y'] + rect1['h'] > rect2['y'] + tolerance)

    def _get_element_bbox(self, element):
        ns = '{http://www.w3.org/2000/svg}'
        tag = element.tag
        if tag in [f'{ns}circle', 'circle']:
            cx = float(element.get('cx', 0))
            cy = float(element.get('cy', 0))
            r = float(element.get('r', 0))
            return {'x': cx - r, 'y': cy - r, 'w': 2 * r, 'h': 2 * r}
        elif tag in [f'{ns}rect', 'rect']:
            return {
                'x': float(element.get('x', 0)),
                'y': float(element.get('y', 0)),
                'w': float(element.get('width', 0)),
                'h': float(element.get('height', 0))
            }
        elif tag in [f'{ns}path', 'path']:
            bbox = self._get_path_bbox(element)
            if bbox:
                x, y, w, h = bbox
                return {'x': x, 'y': y, 'w': w, 'h': h}
        return None

    def _add_filtered_mask_layer(self, parent_group, mask_file, paste_file, pcb_bounds, colors):
        bg_color, pcb_color, silk_color, pad_color = colors
        
        mask_root = self.parse_svg(mask_file)
        if mask_root is None: return
        mask_elements = self._get_drawable_elements(mask_root)
        
        paste_root = self.parse_svg(paste_file)
        paste_bboxes = []
        if paste_root is not None:
            paste_elements = self._get_drawable_elements(paste_root)
            paste_bboxes = [self._get_element_bbox(el) for el in paste_elements if self._get_element_bbox(el) is not None]
        else:
            print(f"⚠️  Paste file not found. Cannot filter mask layer accurately.")

        visible_pads_group = ET.SubElement(parent_group, 'g', {'fill': pad_color, 'stroke': 'none'})
        white_centers_group = ET.SubElement(parent_group, 'g', {
            'fill': bg_color,
            'stroke': 'none'
        })

        ns = '{http://www.w3.org/2000/svg}'
        
        for mask_element in mask_elements:
            mask_bbox = self._get_element_bbox(mask_element)
            if not mask_bbox: continue

            is_coincident = False
            for paste_bbox in paste_bboxes:
                if self._is_overlap(mask_bbox, paste_bbox):
                    is_coincident = True
                    break
            
            if not is_coincident:
                copy = self._create_clean_copy(mask_element)
                visible_pads_group.append(copy)
                
                # Add white centers for different pad types
                if mask_element.tag in [f'{ns}circle', 'circle']:
                    # Handle circular pads
                    cx = float(mask_element.get('cx', 0))
                    cy = float(mask_element.get('cy', 0))
                    r = float(mask_element.get('r', 0))
                    
                    is_mounting_hole = self._is_mounting_hole(mask_element, pcb_bounds)
                    
                    if is_mounting_hole or (0.2 < r < 1.2):
                        hole_radius = r * 0.75 if is_mounting_hole else r * 0.55
                        ET.SubElement(white_centers_group, 'circle', {
                            'cx': str(cx),
                            'cy': str(cy),
                            'r': str(hole_radius)
                        })
                
                elif mask_element.tag in [f'{ns}rect', 'rect']:
                    x = float(mask_element.get('x', 0))
                    y = float(mask_element.get('y', 0))
                    w = float(mask_element.get('width', 0))
                    h = float(mask_element.get('height', 0))
                    cx = x + w / 2
                    cy = y + h / 2
                    is_corner_pad = self._is_near_corner(mask_element, pcb_bounds)
                    
                    if is_corner_pad:
                        hole_radius = min(w, h) * 0.7
                        ET.SubElement(white_centers_group, 'circle', {
                            'cx': str(cx),
                            'cy': str(cy),
                            'r': str(hole_radius)
                        })
                    elif min(w, h) > 0.4 and min(w, h) < 1.5:
                        hole_radius = min(w, h) * 0.8
                        ET.SubElement(white_centers_group, 'circle', {
                            'cx': str(cx),
                            'cy': str(cy),
                            'r': str(hole_radius)
                        })
                
                elif mask_element.tag in [f'{ns}path', 'path']:
                    bbox = self._get_path_bbox(mask_element)
                    if bbox:
                        x, y, w, h = bbox
                        cx = x + w / 2
                        cy = y + h / 2
                        is_corner_pad = self._is_near_corner(mask_element, pcb_bounds)
                        
                        if is_corner_pad or (min(w, h) > 0.4 and min(w, h) < 1.8):
                            hole_radius = min(w, h) * 0.33
                            ET.SubElement(white_centers_group, 'circle', {
                                'cx': str(cx),
                                'cy': str(cy),
                                'r': str(hole_radius)
                            })
    
    def combine_all_layers(self, layer_files, output_file, side, colors, components=None, component_placer=None):
        bg_color, pcb_color, silk_color, pad_color = colors
        edgecut_root = self.parse_svg(layer_files["edge"])
        if edgecut_root is None:
            print(f"❌ Failed to parse edge cuts file")
            return False
        x, y, width, height = self._calculate_bounds(edgecut_root)
        pcb_bounds = (x, y, width, height)
        origin_x = x
        origin_y = y
        padding = 2.0
        is_landscape = width > height
        if is_landscape:
            rotated_width, rotated_height = height, width
            center_x, center_y = x + width / 2, y + height / 2
            new_x, new_y = center_x - rotated_width / 2, center_y - rotated_height / 2
            view_x, view_y = new_x - padding, new_y - padding
            view_width, view_height = rotated_width + padding * 2, rotated_height + padding * 2
        else:
            view_x, view_y = x - padding, y - padding
            view_width, view_height = width + padding * 2, height + padding * 2
        output_svg = ET.Element('svg', nsmap={None: 'http://www.w3.org/2000/svg'})
        output_svg.set('width', '150mm')
        output_svg.set('height', '250mm')
        output_svg.set('viewBox', f"{view_x} {view_y} {view_width} {view_height}")
        main_group = output_svg
        if is_landscape:
            main_group = ET.SubElement(output_svg, 'g')
            center_x = x + width / 2
            main_group.set('transform', f'rotate(-90, {center_x}, {center_y})')
        path_data, mounting_holes = self._create_pcb_base(main_group, edgecut_root, pcb_bounds, colors)
        transform_group = ET.SubElement(main_group, 'g')
        if side == 'bottom':
            center_x = x + width / 2
            center_y = y + height / 2
            transform_group.set('transform', f'rotate(180, {center_x}, {center_y}) translate({2 * center_x}, 0) scale(-1, 1)')
        
        self._add_pcb_layers(transform_group, layer_files, side, colors, pcb_bounds)
        
        mask_file = layer_files.get("f_mask") if side == 'top' else layer_files.get("b_mask")
        paste_file = layer_files.get("f_paste") if side == 'top' else layer_files.get("b_paste")
        if mask_file and Path(mask_file).exists():
             self._add_filtered_mask_layer(transform_group, mask_file, paste_file, pcb_bounds, colors)

        if components and component_placer:
            self._add_component_placement(main_group, components, component_placer, origin_x, origin_y, pcb_bounds, side)

        final_outline_group = ET.SubElement(main_group, 'g', {
            'fill': 'none',
            'stroke': pcb_color,
            'stroke-width': '0.2'
        })
        final_outline_group.append(ET.Element('path', {'d': path_data}))
        for hole in mounting_holes:
            hole_outline = ET.Element(hole.tag, dict(hole.attrib))
            hole_outline.set('fill', 'none')
            hole_outline.set('stroke', pcb_color)
            hole_outline.set('stroke-width', '0.2')
            final_outline_group.append(hole_outline)
        try:
            svg_bytes = ET.tostring(output_svg, pretty_print=True, xml_declaration=True, encoding='utf-8')
            with open(output_file, 'wb') as f:
                f.write(svg_bytes)
            return True
        except Exception as e:
            print(f"❌ Failed to save SVG: {e}")
            return False

    def _add_pcb_layers(self, parent_group, layer_files, side, colors, pcb_bounds):
        bg_color, pcb_color, silk_color, pad_color = colors
        
        silk_file = layer_files.get("f_silk") if side == 'top' else layer_files.get("b_silk")
        if silk_file and Path(silk_file).exists():
            silkscreen_root = self.parse_svg(silk_file)
            if silkscreen_root is not None:
                silkscreen_elements = self._get_drawable_elements(silkscreen_root)
                ns = '{http://www.w3.org/2000/svg}'
                silkscreen_container_group = ET.SubElement(parent_group, 'g', {'fill': silk_color, 'stroke': 'none'})

                for element in silkscreen_elements:
                    copy = self._create_clean_copy(element)
                    if element.tag in [f'{ns}circle', 'circle']:
                        r = float(element.get('r', 0))
                        is_logo_outline = r > 2.5 and not self._is_mounting_hole(element, pcb_bounds)
                        if is_logo_outline:
                            copy.set('fill', 'none')
                            copy.set('stroke', silk_color)
                            copy.set('stroke-width', '0.15')
                        else:
                            copy.set('fill', silk_color)
                            copy.set('stroke', 'none')
                    else:
                        copy.set('fill', silk_color)
                        copy.set('stroke', 'none')
                    silkscreen_container_group.append(copy)

        paste_file = layer_files.get("f_paste") if side == 'top' else layer_files.get("b_paste")
        if paste_file and Path(paste_file).exists():
            paste_root = self.parse_svg(paste_file)
            if paste_root is not None:
                paste_elements = self._get_drawable_elements(paste_root)
                paste_container_group = ET.SubElement(parent_group, 'g', {
                    'fill': '#C0C0C0',
                    'fill-opacity': '0.0'
                })
                for element in paste_elements:
                    paste_container_group.append(self._create_clean_copy(element))

    
    def _add_component_placement(self, parent_group, components, component_placer, pos_origin_x, pos_origin_y, pcb_bounds, side):
        placed_components = set()
        components_group = ET.SubElement(parent_group, 'g', {'id': f'{side}_components'})
        side_components = [comp for comp in components if comp.get('side', 'top').lower() == side.lower()]

        for comp in side_components:
            ref = comp['reference']
            if ref in placed_components:
                continue
            placed_components.add(ref)
            csv_x, csv_y = comp['x'], comp['y']
            svg_x = pos_origin_x + csv_x
            svg_y = pos_origin_y + (pcb_bounds[3] - csv_y)
            svg_file = component_placer.find_component_svg(comp)
            if svg_file and svg_file.exists():
                comp_svg = component_placer.parse_svg(svg_file)
                if comp_svg is not None:
                    center_x, center_y, width, height = component_placer.get_component_bounds(comp_svg)
                    final_rotation = component_placer.get_component_rotation(comp)
                    scale = component_placer.calculate_component_scale(comp, pcb_bounds)
                    scaled_width, scaled_height = width * scale, height * scale
                    
                    svg_data = svg_file.read_bytes()
                    base64_data = base64.b64encode(svg_data).decode('utf-8')
                    data_uri = f"data:image/svg+xml;base64,{base64_data}"
                    
                    comp_element = ET.Element('image', {
                        'id': f"comp_{ref}",
                        'href': data_uri,
                        'width': str(scaled_width),
                        'height': str(scaled_height),
                    })
                    transforms = [
                        f"translate({svg_x}, {svg_y})",
                        f"rotate({-final_rotation})",
                        f"translate({-scaled_width / 2}, {-scaled_height / 2})"
                    ]
                    comp_element.set('transform', ' '.join(transforms))
                    components_group.append(comp_element)
                else:
                    print(f"❌ Failed to parse SVG for {ref}")
            else:
                print(f"❌ Missing SVG for {ref}")

    def combine_svgs_as_images(self, top_svg_path, bottom_svg_path, output_path, bg_color="#1a1a1a", padding=10):
        try:
            top_root = self.parse_svg(top_svg_path)
            bottom_root = self.parse_svg(bottom_svg_path)
            if top_root is None or bottom_root is None:
                return False

            vb_top = [float(n) for n in top_root.get('viewBox').split()]
            vb_bottom = [float(n) for n in bottom_root.get('viewBox').split()]
            w_top, h_top = vb_top[2], vb_top[3]
            w_bottom, h_bottom = vb_bottom[2], vb_bottom[3]

            new_width = w_top + padding + w_bottom
            new_height = max(h_top, h_bottom)

            combined_svg = ET.Element('svg', nsmap={None: 'http://www.w3.org/2000/svg'})
            combined_svg.set('width', '300mm')
            combined_svg.set('height', '150mm')
            combined_svg.set('viewBox', f"0 0 {new_width} {new_height}")

            ET.SubElement(combined_svg, 'rect', {
                'x': '0', 'y': '0', 'width': str(new_width), 'height': str(new_height), 'fill': bg_color
            })

            top_data = base64.b64encode(top_svg_path.read_bytes()).decode('utf-8')
            ET.SubElement(combined_svg, 'image', {
                'x': '0', 'y': '0',
                'width': str(w_top), 'height': str(h_top),
                'href': f"data:image/svg+xml;base64,{top_data}"
            })

            bottom_data = base64.b64encode(bottom_svg_path.read_bytes()).decode('utf-8')
            ET.SubElement(combined_svg, 'image', {
                'x': str(w_top + padding), 'y': '0',
                'width': str(w_bottom), 'height': str(h_bottom),
                'href': f"data:image/svg+xml;base64,{bottom_data}"
            })

            svg_bytes = ET.tostring(combined_svg, pretty_print=True, xml_declaration=True, encoding='utf-8')
            with open(output_path, 'wb') as f:
                f.write(svg_bytes)
            return True
        except Exception as e:
            print(f"❌ Failed to combine SVGs: {e}")
            return False


def find_layer_files(folder_path):
    folder = Path(folder_path)
    if not folder.exists():
        print(f"❌ Folder not found: {folder_path}")
        return {}
    files = {
        "edge": next(folder.glob('*-Edge_Cuts.svg'), None),
        "f_mask": next(folder.glob('*-F_Mask.svg'), None),
        "b_mask": next(folder.glob('*-B_Mask.svg'), None),
        "f_silk": next(folder.glob('*-F_Silkscreen.svg'), None),
        "b_silk": next(folder.glob('*-B_Silkscreen.svg'), None),
        "f_paste": next(folder.glob('*-F_Paste.svg'), None),
        "b_paste": next(folder.glob('*-B_Paste.svg'), None),
        "pos": next(folder.glob('*-pos.csv'), None),
    }
    print("🔎 Searching for layer files...")
    for key, file in files.items():
        if file:
            print(f"   - ✅ Found {key}: {file.name}")
        else:
            print(f"   - ❌ Missing {key} file")
    print() # Add a newline for spacing
    return files


def create_pcb_renders(gerber_folder, component_folder, colors):
    gerber_path = Path(gerber_folder)
    output_path = gerber_path / "output"
    output_path.mkdir(exist_ok=True)
    layer_files = find_layer_files(gerber_path)
    if not layer_files.get("edge"):
        print("❌ Edge cuts file not found! Cannot proceed.")
        return False
    if not layer_files.get("pos"):
        print("❌ Position CSV file not found! Cannot place components.")
        return False
    component_placer = ComponentPlacer(component_folder, gerber_folder)
    components = component_placer.load_csv_file(layer_files["pos"])
    if not components:
        print("❌ No components loaded from CSV!")
        return False
    svg_processor = SVGProcessor()
    success = True
    top_output = output_path / "pcb_top_with_components.svg"
    if not svg_processor.combine_all_layers(layer_files, top_output, 'top', colors, components, component_placer):
        success = False
    bottom_output = output_path / "pcb_bottom_with_components.svg"
    if not svg_processor.combine_all_layers(layer_files, bottom_output, 'bottom', colors, components, component_placer):
        success = False

    both_output = None
    if success:
        both_output = output_path / "pcb_combined_view.svg"
        if not svg_processor.combine_svgs_as_images(top_output, bottom_output, both_output, colors[0]):
             print("⚠️  Could not generate combined view, but individual files were created.")

    if success:
        print(f"📁 Output folder: {output_path.absolute()}")
        if top_output.exists():
            print(f"   - Top view: {top_output.name}")
        if bottom_output.exists():
            print(f"   - Bottom view: {bottom_output.name}")
        if both_output and both_output.exists():
            print(f"   - Combined view: {both_output.name}")
        print(f"⚙️  Component config: {component_placer.config_path}")
    else:
        print(f"\n❌ Some renders failed to generate.")
    return success


def main():
    parser = argparse.ArgumentParser(description="PCB Renderer with Component Placement")
    parser.add_argument("--files", "-f", required=True, help="Path to Gerber files folder")
    parser.add_argument("--components", "-c", required=True, help="Path to component SVG folder")
    parser.add_argument("--config-only", action="store_true", help="Only generate component config without rendering")
    parser.add_argument("--colors", nargs=4, metavar=('BG', 'PCB', 'SILK', 'PAD'),
                        help="Set colors: BG PCB SILK PAD (e.g., '#1a1a1a' '#2d5a3d' '#ffffff' '#ffd700').")
    args = parser.parse_args()
    print("Forge")
    
    if args.config_only:
        gerber_path = Path(args.files)
        layer_files = find_layer_files(gerber_path)
        if not layer_files.get("pos"):
            print("❌ Position CSV file not found!")
            return False
        component_placer = ComponentPlacer(args.components, args.files)
        components = component_placer.load_csv_file(layer_files["pos"])
        if components:
            component_placer._print_mapping_summary()
            print(f"\n✅ Component configuration generated!")
            print(f"📁 Edit {component_placer.config_path} to customize mappings")
        else:
            print("❌ Failed to generate component configuration")
        return True
    else:
        colors = args.colors or ('#1a1a1a', '#2d5a3d', '#ffffff', '#ffd700')
        return create_pcb_renders(args.files, args.components, colors)


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
