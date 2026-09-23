import { CanMatchFn } from '@angular/router';
import { environment } from '../../../environments/environment';

export const phase3ResultsGuard: CanMatchFn = () => environment.features.phase3Results;
