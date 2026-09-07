import { Routes } from '@angular/router';
import { Login } from './pages/login/login';
import { authGuard } from './core/guards/auth-guard';
import { AppLayout } from './layout/app-layout/app-layout';
import { NewItem } from './pages/new-item/new-item';
import { Labels } from './pages/labels/labels';
import { Dashboard } from './pages/dashboard/dashboard';
import { LearningItemView } from './pages/learning-item-view/learning-item-view';
import { Playground } from './pages/playground/playground';
import { Canvas } from './pages/canvas/canvas';

export const routes: Routes = [
    {
        path: '',
        component: Login
    },
    {
        path: 'app',

        component: AppLayout,

        canActivate: [authGuard],

        children: [

        {
            path: 'dashboard',
            component: Dashboard
        },
        {
            path: 'new-item',
            component: NewItem
        },
        {
            path: 'labels',
            component: Labels
        },
        {
            path: 'learning-items/:id/questions',
            loadComponent: () => import('./pages/learning-item-questions/learning-item-questions').then((module) => module.LearningItemQuestions)
        },
        {
            path: 'learning-items/:id',
            component: LearningItemView
        },
        {
            path: 'revise',
            loadComponent: () => import('./pages/revise/revise').then((module) => module.Revise)
        },
        {
            path: 'revision-sessions/:sessionId',
            loadComponent: () => import('./pages/revision-session/revision-session').then((module) => module.RevisionSession)
        },
        {
            path: 'revision-sessions/:sessionId/result',
            loadComponent: () => import('./pages/revision-result/revision-result').then((module) => module.RevisionResult)
        },
        {
            path: 'playground',
            component: Playground
        },
        {
            path: 'canvas',
            component: Canvas
        }

        ]
    }
];
