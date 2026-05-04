import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { DiagnosticResult } from './diagnostics.models';

@Injectable({ providedIn: 'root' })
export class DiagnosticsService {
  private readonly apiUrl = '/api';

  constructor(private readonly http: HttpClient) {}

  runDiagnostics(logPath?: string): Observable<DiagnosticResult> {
    return this.http.post<DiagnosticResult>(`${this.apiUrl}/diagnostics/run`, {
      log_path: logPath || null,
    });
  }

  getLatest(): Observable<DiagnosticResult> {
    return this.http.get<DiagnosticResult>(`${this.apiUrl}/diagnostics/latest`);
  }

  getGraphStatus(): Observable<Pick<DiagnosticResult, 'graph_status' | 'current_step' | 'steps'>> {
    return this.http.get<Pick<DiagnosticResult, 'graph_status' | 'current_step' | 'steps'>>(
      `${this.apiUrl}/graph/status`,
    );
  }
}
