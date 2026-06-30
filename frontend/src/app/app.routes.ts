import { Routes } from '@angular/router';
import { Login } from './pages/login/login';
import { authGuard } from './core/guards/auth-guard';
import { AppLayout } from './layout/app-layout/app-layout';
import { NewItem } from './pages/new-item/new-item';
import { Labels } from './pages/labels/labels';
import { Dashboard } from './pages/dashboard/dashboard';
import { LearningItemView } from './pages/learning-item-view/learning-item-view';

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
            path: 'learning-items/:id',
            component: LearningItemView
        }

        ]
    }
];
