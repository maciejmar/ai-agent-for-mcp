import { bootstrapApplication } from '@angular/platform-browser';
import { provideHttpClient } from '@angular/common/http';
import { DiagnosticsDashboardComponent } from './app/diagnostics-dashboard.component';

bootstrapApplication(DiagnosticsDashboardComponent, {
  providers: [provideHttpClient()],
}).catch((err) => console.error(err));
