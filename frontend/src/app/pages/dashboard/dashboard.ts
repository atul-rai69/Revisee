import { CommonModule } from '@angular/common';
import { Component, OnInit, signal, ChangeDetectorRef } from '@angular/core';
import { Router } from '@angular/router';
import {
  DashboardService,
  DashboardSummary,
  LearningItemsSummary,
} from '../../core/services/dashboard-service';

import { LearningItem } from '../../core/services/learning-item';
import { ToasterService } from '../../core/services/toaster.service';

interface DashboardStat {
  title: string;
  detail: string;
  icon: string;
  tone: 'teal' | 'amber' | 'green' | 'blue';
  metric: 'totalItems' | 'totalLabels' | 'itemsReviewed' | 'loginStreak';
}

interface DashboardItem {
  id: number,
  title: string;
  description: string;
  image: string;
  labels: string[];
  notes: number;
  images: number;
  pdfs: number;
  time: string;
}

interface TopicOverview {
  name: string;
  icon: string;
  count: number;
  progress: number;
}

interface RecentlyViewedItem {
  title: string;
  image: string;
  labels: string[];
  time: string;
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class Dashboard implements OnInit {

  username = signal('');
  totalItems = signal(0);
  totalLabels = signal(0);
  loginStreak = signal(0);
  itemsReviewed = signal(42);

  constructor(private dashboardService: DashboardService,private router: Router, private learningItemService: LearningItem, private toaster: ToasterService,private cdr: ChangeDetectorRef){}

  ngOnInit(): void {

    this.dashboardSummaryResponse();
    this.learningItemsSummaryResponse();
    console.log(this.recentItems);
  }

  stats: DashboardStat[] = [
    {
      title: 'Total Items',
      detail: 'Learning items',
      icon: 'ph ph-file-text',
      tone: 'teal',
      metric: 'totalItems',
    },
    {
      title: 'Total Labels',
      detail: 'Organized labels',
      icon: 'ph ph-star',
      tone: 'amber',
      metric: 'totalLabels',
    },
    {
      title: 'Items Reviewed',
      detail: '+8 this week',
      icon: 'ph ph-calendar-check',
      tone: 'green',
      metric: 'itemsReviewed',
    },
    {
      title: 'Study Streak',
      detail: 'Keep it up!',
      icon: 'ph ph-chart-bar',
      tone: 'blue',
      metric: 'loginStreak',
    },
  ];

  recentItems: DashboardItem[] = [
    {
      id: 1,
      title: 'The Cell Structure',
      description: 'Key components of a cell and their functions.',
      image:
        'https://images.unsplash.com/photo-1576086213369-97a306d36557?auto=format&fit=crop&w=420&q=80',
      labels: ['Biology', 'Cell Biology', 'Class 11'],
      notes: 2,
      images: 1,
      pdfs: 1,
      time: '2h ago',
    },
    {
      id: 2,
      title: 'Einstein’s Mass-Energy Equivalence',
      description: 'E = mc2 and its applications in modern physics.',
      image:
        'https://images.unsplash.com/photo-1636466497217-26a8cbeaf0aa?auto=format&fit=crop&w=420&q=80',
      labels: ['Physics', 'Mechanics', 'Class 12'],
      notes: 1,
      images: 1,
      pdfs: 1,
      time: '1 day ago',
    },
    {
      id: 3,
      title: 'Photosynthesis Process',
      description: 'Steps of photosynthesis and factors affecting it.',
      image:
        'https://images.unsplash.com/photo-1456735190827-d1262f71b8a3?auto=format&fit=crop&w=420&q=80',
      labels: ['Biology', 'Botany', 'Class 11'],
      notes: 3,
      images: 2,
      pdfs: 1,
      time: '2 days ago',
    },
    {
      id: 4,
      title: 'Indian Freedom Struggle - 1857',
      description: 'Causes, events and impact of the 1857 revolt.',
      image:
        'https://images.unsplash.com/photo-1580137189272-c9379f8864fd?auto=format&fit=crop&w=420&q=80',
      labels: ['History', 'India', 'Class 10'],
      notes: 2,
      images: 1,
      pdfs: 1,
      time: '3 days ago',
    },
    {
      id: 5,
      title: 'Integrals - Basics and Formulas',
      description: 'Important formulas and basic concepts of integration.',
      image:
        'https://images.unsplash.com/photo-1635070041078-e363dbe005cb?auto=format&fit=crop&w=420&q=80',
      labels: ['Mathematics', 'Calculus', 'Class 12'],
      notes: 1,
      images: 0,
      pdfs: 1,
      time: '4 days ago',
    },
  ];

  topics: TopicOverview[] = [
    { name: 'Biology', icon: 'ph ph-flask', count: 24, progress: 94 },
    { name: 'Physics', icon: 'ph ph-atom', count: 20, progress: 72 },
    { name: 'Mathematics', icon: 'ph ph-function', count: 18, progress: 62 },
    { name: 'History', icon: 'ph ph-bank', count: 15, progress: 48 },
    { name: 'Chemistry', icon: 'ph ph-test-tube', count: 12, progress: 35 },
  ];

  recentlyViewed: RecentlyViewedItem[] = [
    {
      title: 'Chemical Bonding',
      image:
        'https://images.unsplash.com/photo-1532187643603-ba119ca4109e?auto=format&fit=crop&w=160&q=80',
      labels: ['Chemistry', 'Class 11'],
      time: '5h ago',
    },
    {
      title: 'Quadratic Equations',
      image:
        'https://images.unsplash.com/photo-1596495578065-6e0763fa1178?auto=format&fit=crop&w=160&q=80',
      labels: ['Mathematics', 'Class 10'],
      time: '1 day ago',
    },
    {
      title: 'Plant Tissues',
      image:
        'https://images.unsplash.com/photo-1501004318641-b39e6451bec6?auto=format&fit=crop&w=160&q=80',
      labels: ['Biology', 'Botany'],
      time: '2 days ago',
    },
    {
      title: 'Thermodynamics Laws',
      image:
        'https://images.unsplash.com/photo-1607988795691-3d0147b43231?auto=format&fit=crop&w=160&q=80',
      labels: ['Physics', 'Thermodynamics'],
      time: '3 days ago',
    },
  ];

  private dashboardSummaryResponse():void{
    this.dashboardService.getDashboardSummary().subscribe({
      next: (data) => {
        this.username.set(data.username);
        this.totalItems.set(data.total_items);
        this.totalLabels.set(data.total_labels);
        this.loginStreak.set(data.login_streak);
      },
      error: (err) => console.error(err),
    });
  }

  private bindDashboardSummary(data: DashboardSummary): void {
    this.username.set(data.username);
    this.totalItems.set(data.total_items);
    this.totalLabels.set(data.total_labels);
    this.loginStreak.set(data.login_streak);

    console.log(this.username());
    console.log(this.totalItems());
  }

  private learningItemsSummaryResponse():void{
    this.dashboardService.getLearningItemSummary().subscribe({
      next: (response) => {
      this.recentItems = response.data.map((item: any) => ({
        id: item.id,
        title: item.title,
        description: this.stripHtml(item.description_text),

        image:
          item.first_image_url ||
          'assets/images/default-learning-item.png',

        labels: item.labels
          ? item.labels.split(',').map((label: string) => label.trim())
          : [],

        notes: 0, // API doesn't return this

        images: item.image_count ?? 0,

        pdfs: item.pdf_count ?? 0,

        time: this.formatHoursAgo(item.hours_ago),
      }));
      this.cdr.detectChanges();
      console.log(this.recentItems);
    },

      error: (err) => console.error(err),
    });
  }

  private bindLearningItemSummary(item: LearningItemsSummary): DashboardItem {
    return {
      id: item.id,
      title: item.title,
      description: item.description_text,
      image: item.first_image_url,
      labels: this.parseLabels(item.labels),
      notes: 0,
      images: item.image_count,
      pdfs: item.pdf_count,
      time: this.formatHoursAgo(item.hours_ago),
    };
  }

  private parseLabels(labels: string): string[] {
    return labels
      ? labels.split(',').map((label) => label.trim()).filter(Boolean)
      : [];
  }

  private formatHoursAgo(hours: number): string {
    if (hours == 0){
      return "Just Now";
    }
    if (hours < 24) {
      return `${hours}h ago`;
    }

    const days = Math.floor(hours / 24);
    return `${days} ${days === 1 ? 'day' : 'days'} ago`;
  }

  private stripHtml(html: string): string {
    const div = document.createElement('div');
    div.innerHTML = html;
    return div.textContent || '';
  }

  check(): void{
    alert("alert");
    console.log('running')
  }

  deleteItem(id: number):void{

    this.learningItemService.deleteLearningItem(id).subscribe({
       next: () => {
        this.dashboardSummaryResponse();
        this.learningItemsSummaryResponse();
        this.toaster.success('Learning Item Deleted successfully.');
      },
      error: (error) => {
        console.error(error);
        this.toaster.error('Could not delete Item');
      }
    })
  }

  viewLearningItem(id: number){
    this.router.navigate([`app/learning-items/${id}`])
  }
}
