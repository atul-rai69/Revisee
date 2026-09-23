import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth-guard';

export const routes: Routes = [
    {
        path: '',
        loadComponent: () => import('./pages/login/login').then((module) => module.Login),
        title: 'Revisee — Learn. Revise. Remember.'
    },
    {
        path: 'app',

        loadComponent: () => import('./layout/app-layout/app-layout').then((module) => module.AppLayout),

        canActivate: [authGuard],

        children: [
        {
            path: '',
            pathMatch: 'full',
            redirectTo: 'dashboard'
        },
        {
            path: 'dashboard',
            loadComponent: () => import('./pages/dashboard/dashboard').then((module) => module.Dashboard),
            title: 'Home · Revisee'
        },
        {
            // Temporary route alias until the dedicated Library redesign phase.
            path: 'library',
            loadComponent: () => import('./pages/dashboard/dashboard').then((module) => module.Dashboard),
            title: 'Library · Revisee'
        },
        {
            path: 'new-item',
            loadComponent: () => import('./pages/new-item/new-item').then((module) => module.NewItem),
            title: 'Add learning material · Revisee'
        },
        {
            path: 'labels',
            loadComponent: () => import('./pages/labels/labels').then((module) => module.Labels),
            title: 'Topics · Revisee'
        },
        {
            path: 'learning-items/:id/questions',
            loadComponent: () => import('./pages/learning-item-questions/learning-item-questions').then((module) => module.LearningItemQuestions),
            title: 'Question bank · Revisee'
        },
        {
            path: 'learning-items/:id',
            loadComponent: () => import('./pages/learning-item-view/learning-item-view').then((module) => module.LearningItemView),
            title: 'Learning item · Revisee'
        },
        {
            path: 'revise',
            loadComponent: () => import('./pages/revise/revise').then((module) => module.Revise),
            title: 'Revise · Revisee'
        },
        {
            path: 'revision-sessions',
            loadComponent: () => import('./pages/revision-history/revision-history').then((module) => module.RevisionHistory),
            title: 'Revision history · Revisee'
        },
        {
            path: 'analytics',
            loadComponent: () => import('./pages/analytics/analytics').then((module) => module.Analytics),
            title: 'Mastery analytics · Revisee'
        },
        {
            path: 'settings',
            loadComponent: () => import('./pages/settings/settings').then((module) => module.Settings),
            title: 'Settings · Revisee'
        },
        {
            path: 'revision-sessions/:sessionId',
            loadComponent: () => import('./pages/revision-session/revision-session').then((module) => module.RevisionSession),
            title: 'Revision session · Revisee'
        },
        {
            path: 'revision-sessions/:sessionId/result',
            loadComponent: () => import('./pages/revision-result/revision-result').then((module) => module.RevisionResult),
            title: 'Revision result · Revisee'
        },
        {
            path: '**',
            loadComponent: () => import('./pages/not-found/not-found').then((module) => module.NotFound),
            title: 'Page not found · Revisee'
        }
        ]
    },
    {
        path: '**',
        loadComponent: () => import('./pages/not-found/not-found').then((module) => module.NotFound),
        title: 'Page not found · Revisee'
    }
];
