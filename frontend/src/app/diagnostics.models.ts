export interface DiagnosticFinding {
  severity: 'info' | 'warning' | 'critical';
  kind: 'runtime' | 'configuration' | 'resource' | 'network' | 'unknown';
  title: string;
  evidence: string[];
  requires_restart: boolean;
}

export interface Recommendation {
  title: string;
  action: string;
  priority: string;
}

export interface GraphStep {
  name: string;
  status: string;
}

export interface LlmInferenceEngine {
  name: string;
  image: string;
  status: string;
  running: boolean;
  ports: string;
  matched_by: ('name' | 'port')[];
}

export interface LlmInferenceStatus {
  ok?: boolean;
  error?: string;
  result?: {
    engine_count?: number;
    running_count?: number;
    engines?: LlmInferenceEngine[];
    error?: string;
  };
}

export interface DiagnosticResult {
  graph_status: string;
  current_step: string;
  steps: GraphStep[];
  findings: DiagnosticFinding[];
  recommendations: Recommendation[];
  llm_status?: string;
  llm_summary?: string;
  log_snapshot?: {
    path?: string;
    filtered_line_count?: number;
    raw_line_count?: number;
    error?: string;
  };
}
