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

export interface DiagnosticResult {
  graph_status: string;
  current_step: string;
  steps: GraphStep[];
  findings: DiagnosticFinding[];
  recommendations: Recommendation[];
  log_snapshot?: {
    path?: string;
    filtered_line_count?: number;
    raw_line_count?: number;
    error?: string;
  };
}
