import type { DefectClass } from './types';

// Per-class colour palette. Neither benchmark.ipynb nor visualise_defect.ipynb
// defines a per-class mapping (both draw all boxes in red / blue), so this
// palette is defined here and is the single source of truth for the demo. Mirror
// values live in app.css as --c-* custom properties for use from .svelte files.
export const CLASS_COLOR: Record<DefectClass, string> = {
  missing_hole:    '#3EA6FF',
  mouse_bite:      '#F2B33D',
  open_circuit:    '#B26BFF',
  short:           '#E5484D',
  spur:            '#2BD17E',
  spurious_copper: '#FF7B5C'
};

export const CLASS_LABEL: Record<DefectClass, string> = {
  missing_hole:    'Missing hole',
  mouse_bite:      'Mouse bite',
  open_circuit:    'Open circuit',
  short:           'Short',
  spur:            'Spur',
  spurious_copper: 'Spurious copper'
};

export const DEFECT_CLASSES: DefectClass[] = [
  'missing_hole',
  'mouse_bite',
  'open_circuit',
  'short',
  'spur',
  'spurious_copper'
];
