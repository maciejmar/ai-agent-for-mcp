import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DiagnosticsService } from './diagnostics.service';
import { DiagnosticResult, LlmInferenceStatus } from './diagnostics.models';
import { MarkdownPipe } from './markdown.pipe';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule, MarkdownPipe],
  templateUrl: './diagnostics-dashboard.component.html',
  styleUrl: './diagnostics-dashboard.component.css',
})
export class DiagnosticsDashboardComponent {
  logPath = '';
  loading = false;
  result: DiagnosticResult | null = null;
  errorMessage = '';

  llmStatusLoading = false;
  llmStatus: LlmInferenceStatus | null = null;
  llmStatusError = '';

  constructor(private readonly diagnostics: DiagnosticsService) {}

  run(): void {
    this.loading = true;
    this.errorMessage = '';
    this.diagnostics.runDiagnostics(this.logPath).subscribe({
      next: (result) => {
        this.result = result;
        this.loading = false;
      },
      error: () => {
        this.errorMessage = 'Nie udało się uruchomić diagnostyki.';
        this.loading = false;
      },
    });
  }

  checkLlmInferenceStatus(): void {
    this.llmStatusLoading = true;
    this.llmStatusError = '';
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
