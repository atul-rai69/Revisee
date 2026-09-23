import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, signal } from '@angular/core';
import { Router } from '@angular/router';
import { finalize } from 'rxjs';
import { RevisionHistoryItem, RevisionStatus } from '../../core/models/revision.models';
import { RevisionSessionService } from '../../core/services/revision-session.service';

@Component({
  selector: 'app-revision-history',
  imports: [CommonModule],
  templateUrl: './revision-history.html',
  styleUrl: './revision-history.css',
})
export class RevisionHistory implements OnInit {
  readonly filterOptions: readonly (RevisionStatus | 'ALL')[] = ['ALL', 'COMPLETED', 'IN_PROGRESS'];
  readonly sessions = signal<RevisionHistoryItem[]>([]);
  readonly total = signal(0);
  readonly loading = signal(false);
  readonly error = signal(false);
  readonly filter = signal<RevisionStatus | 'ALL'>('ALL');
  readonly offset = signal(0);
  readonly limit = 10;
  readonly pageNumber = computed(() => Math.floor(this.offset() / this.limit) + 1);
  readonly pageCount = computed(() => Math.max(1, Math.ceil(this.total() / this.limit)));

  constructor(
    private readonly service: RevisionSessionService,
    private readonly router: Router,
  ) {}

  ngOnInit(): void { this.load(); }

  load(): void {
    if (this.loading()) return;
    this.loading.set(true);
    this.error.set(false);
    const selectedFilter = this.filter();
    const status: RevisionStatus | undefined = selectedFilter === 'ALL'
      ? undefined
      : selectedFilter;
    this.service.getHistory({ status, limit: this.limit, offset: this.offset() })
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (page) => { this.sessions.set(page.items); this.total.set(page.total); },
        error: () => this.error.set(true),
      });
  }

  setFilter(filter: RevisionStatus | 'ALL'): void {
    if (this.filter() === filter) return;
    this.filter.set(filter);
    this.offset.set(0);
    this.load();
  }

  previous(): void { this.offset.update((value) => Math.max(0, value - this.limit)); this.load(); }
  next(): void { if (this.offset() + this.limit < this.total()) { this.offset.update((value) => value + this.limit); this.load(); } }
  open(session: RevisionHistoryItem): void {
    const suffix = session.status === 'COMPLETED' ? ['result'] : [];
    void this.router.navigate(['/app/revision-sessions', session.session_id, ...suffix]);
  }
  startRevision(): void { void this.router.navigate(['/app/revise']); }
  strategyLabel(value: string): string { return ({ RANDOM: 'Quick', LABEL: 'Topic', SMART: 'SMART' } as Record<string, string>)[value] ?? value; }
  formatDate(value: string | null): string { return value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : 'Date unavailable'; }
  formatDuration(seconds: number | null): string { if (seconds === null) return '—'; const minutes = Math.floor(seconds / 60); return minutes ? `${minutes}m ${seconds % 60}s` : `${seconds}s`; }
  topicNames(session: RevisionHistoryItem): string { return session.labels?.map((label) => label.label_name).join(', ') ?? ''; }
}
