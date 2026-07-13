import { CommonModule } from '@angular/common';
import { Component, OnDestroy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subscription, interval } from 'rxjs';
import { switchMap } from 'rxjs/operators';
import { DiagnosticsService } from './diagnostics.service';
import { DiagnosticResult, GraphStep, LlmInferenceStatus } from './diagnostics.models';
import { MarkdownPipe } from './markdown.pipe';

interface ProgressStepView {
  key: string;
  label: string;
  state: 'done' | 'active' | 'pending';
}

const STEP_ORDER: { key: string; label: string }[] = [
  { key: 'fetch_logs', label: 'Pobieranie logów i metryk' },
  { key: 'analyze', label: 'Analiza wyników' },
  { key: 'suggest_fixes', label: 'Rekomendacje (LLM)' },
];

const GRAPH_STATUS_LABELS: Record<string, string> = {
  idle: 'bezczynny',
  started: 'uruchomiony',
  logs_and_metrics_collected: 'logi i metryki zebrane',
  analysis_completed: 'analiza zakończona',
  completed: 'zakończono',
};

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule, MarkdownPipe],
  templateUrl: './diagnostics-dashboard.component.html',
  styleUrl: './diagnostics-dashboard.component.css',
})
export class DiagnosticsDashboardComponent implements OnDestroy {
  logPath = '';
  loading = false;
  result: DiagnosticResult | null = null;
  errorMessage = '';

  llmStatusLoading = false;
  llmStatus: LlmInferenceStatus | null = null;
  llmStatusError = '';

  liveSteps: GraphStep[] = [];
  liveGraphStatus = 'idle';
  private pollSubscription: Subscription | null = null;

  constructor(private readonly diagnostics: DiagnosticsService) {}

  run(): void {
    this.loading = true;
    this.errorMessage = '';
    this.llmStatus = null;
    this.llmStatusError = '';
    this.liveSteps = [];
    this.liveGraphStatus = 'started';
    this.startPolling();
    this.diagnostics.runDiagnostics(this.logPath).subscribe({
      next: (result) => {
        this.result = result;
        this.loading = false;
        this.stopPolling();
      },
      error: () => {
        this.errorMessage = 'Nie udało się uruchomić diagnostyki.';
        this.loading = false;
        this.stopPolling();
      },
    });
  }

  ngOnDestroy(): void {
    this.stopPolling();
  }

  get displayGraphStatus(): string {
    const raw = this.loading ? this.liveGraphStatus : this.result?.graph_status || 'idle';
    return GRAPH_STATUS_LABELS[raw] ?? raw;
  }

  get progressSteps(): ProgressStepView[] {
    const doneKeys = new Set((this.loading ? this.liveSteps : this.result?.steps ?? []).map((step) => step.name));
    let activeAssigned = false;
    return STEP_ORDER.map((step) => {
      let state: ProgressStepView['state'] = 'pending';
      if (doneKeys.has(step.key)) {
        state = 'done';
      } else if (this.loading && !activeAssigned) {
        state = 'active';
        activeAssigned = true;
      }
      return { ...step, state };
    });
  }

  private startPolling(): void {
    this.pollSubscription = interval(600)
      .pipe(switchMap(() => this.diagnostics.getGraphStatus()))
      .subscribe({
        next: (status) => {
          this.liveSteps = status.steps ?? [];
          this.liveGraphStatus = status.graph_status || this.liveGraphStatus;
        },
      });
  }

  private stopPolling(): void {
    this.pollSubscription?.unsubscribe();
    this.pollSubscription = null;
  }

  checkLlmInferenceStatus(): void {
    this.llmStatusLoading = true;
    this.llmStatusError = '';
    this.result = null;
    this.errorMessage = '';
    this.diagnostics.getLlmInferenceStatus().subscribe({
      next: (status) => {
        this.llmStatus = status;
        this.llmStatusLoading = false;
      },
      error: () => {
        this.llmStatusError = 'Nie udało się sprawdzić aplikacji do inferencji LLM.';
        this.llmStatusLoading = false;
      },
    });
  }

  badgeClass(value: string): string {
    return `badge badge-${value}`;
  }
}
