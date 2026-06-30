import { Component } from '@angular/core';
import { Sidebar } from '../../shared/components/sidebar/sidebar/sidebar';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-app-layout',
  imports: [Sidebar, RouterOutlet],
  templateUrl: './app-layout.html',
  styleUrl: './app-layout.css',
})
export class AppLayout {

}
