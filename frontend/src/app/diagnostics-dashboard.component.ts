import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DiagnosticsService } from './diagnostics.service';
import { DiagnosticResult } from './diagnostics.models';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './diagnostics-dashboard.component.html',
  styleUrl: './diagnostics-dashboard.component.css',
})
export class DiagnosticsDashboardComponent {
  logPath = '';
  loading = false;
  result: DiagnosticResult | null = null;
  errorMessage = '';

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

  badgeClass(value: string): string {
    return `badge badge-${value}`;
  }
}
