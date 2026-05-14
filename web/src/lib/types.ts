export type DefectClass =
  | 'missing_hole'
  | 'mouse_bite'
  | 'open_circuit'
  | 'short'
  | 'spur'
  | 'spurious_copper';

export interface SampleEntry {
  file: string;
  layout_id: string;
  expected_class: DefectClass;
  width: number;
  height: number;
}

export interface DetectionBox {
  x: number;
  y: number;
  w: number;
  h: number;
  class: DefectClass;
  confidence: number;
}

export interface DetectResponse {
  verdict: 'PASS' | 'FAIL';
  boxes: DetectionBox[];
  timing_ms: {
    register: number;
    propose: number;
    classify: number;
    total: number;
  };
}

export interface ColdStartResponse {
  cold_start: true;
  eta_ms: number;
}

export interface RateLimitedResponse {
  rate_limited: true;
  retry_after_s: number;
}

export interface ErrorResponse {
  error: string;
}

export type ApiResponse =
  | DetectResponse
  | ColdStartResponse
  | RateLimitedResponse
  | ErrorResponse;

export interface QueueTile {
  /** unique uuid for keyed transitions */
  id: string;
  /** sample manifest entry this tile represents */
  sample: SampleEntry;
  /** L{layout}-{YYYYMMDD}-{seq:04d} */
  serial: string;
  /** ms since epoch when the tile arrived in the queue */
  arrived_at: number;
}

export interface CompletedRun {
  id: string;
  tile: QueueTile;
  response: DetectResponse;
  finished_at: number;
}

export type BayState =
  | { kind: 'idle' }
  | { kind: 'warming'; eta_ms: number; started_at: number }
  | { kind: 'scanning'; tile: QueueTile; started_at: number; server_timing?: DetectResponse['timing_ms'] }
  | { kind: 'result'; tile: QueueTile; response: DetectResponse }
  | { kind: 'error'; tile: QueueTile; message: string; attempt: number };

export type NodeHealth = 'WARM' | 'COLD' | 'UNKNOWN';
export type ConveyorMode = 'AUTOMATIC' | 'MANUAL';
