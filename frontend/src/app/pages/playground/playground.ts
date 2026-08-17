import { Component, AfterViewInit, ElementRef, ViewChild } from '@angular/core';

@Component({
  selector: 'app-playground',
  imports: [],
  templateUrl: './playground.html',
  styleUrl: './playground.css',
})
export class Playground implements AfterViewInit{

  mouseX = 0;
  mouseY = 0;

  previousMouseX = 0;
  previousMouseY = 0;

  velocity = 0;
  glowSize = 75;

  glowX = 0;
  glowY = 0;


  arrowRotation = 0;  


  @ViewChild('moon')
  moonElement!: ElementRef<HTMLElement>;


  @ViewChild('arrow')
  arrowElement!: ElementRef<HTMLImageElement>;

  moonScale = 1;
  moonBoxShadow = '0 0 80px rgba(255,255,255,0.15)';


  /* ==========================================================
  MOON STATE
  ----------------------------------------------------------
  Offset from the moon's original CSS position.
  Base position stays in CSS.
  Animation only changes this offset.
  ========================================================== */

  moonOffsetY = 0;


  /* ==========================================================
  SCENE CLOCK
  ----------------------------------------------------------
  This continuously increases every frame.
  Every time-based animation (Moon, Clouds, Stars, etc.)
  will use this same clock.
  ========================================================== */

  time = 0;





  ngAfterViewInit(): void {

    this.animate();

  }

  /* ==========================================================
  MOUSE MOVE
  ----------------------------------------------------------
  Updates mouse position.
  Then asks the Glow to update itself.
  ========================================================== */

  onMouseMove(event: MouseEvent): void {

    const hero = event.currentTarget as HTMLElement;

    const rect = hero.getBoundingClientRect();

    this.mouseX = event.clientX - rect.left;
    this.mouseY = event.clientY - rect.top;

    const deltaX = this.mouseX - this.previousMouseX;
    const deltaY = this.mouseY - this.previousMouseY;


    this.previousMouseX = this.mouseX;
    this.previousMouseY = this.mouseY;

    this.velocity = Math.hypot(deltaX, deltaY);

    console.log(this.velocity);

  }


  /* ==========================================================
  ANIMATION LOOP
  ----------------------------------------------------------
  Think of this as the heartbeat of the Hero.
  Browser
  ↓
  Animate Scene
  ↓
  Browser
  ↓
  Animate Scene
  ↓
  Repeat forever...
  ========================================================== */

  private animate(): void {

    // Advance scene time
    this.time += 0.02;

    // Update all animation systems
    this.updateGlow();
    this.updateMoon();

    this.updateMoonGlow();

    this.updateArrow();

    // Continue animation loop
    requestAnimationFrame(() => this.animate());

  }


  /* ==========================================================
  GLOW UPDATE
  ----------------------------------------------------------
  Version 1

  Instantly moves to cursor.

  Version 2
  Will use LERP.
  ========================================================== */

  updateGlow(): void {

    this.glowX = this.lerp(
      this.glowX,
      this.mouseX,
      0.1
    );

    this.glowY = this.lerp(
      this.glowY,
      this.mouseY,
      0.1
    );

    const targetGlowSize = 75 + this.velocity * 3;

    this.glowSize += (targetGlowSize - this.glowSize) * 0.12;

  }



  /* ==========================================================
  MOON SYSTEM
  ----------------------------------------------------------
  Floating animation using Sine.
  Formula:
  Offset = sin(time) × amplitude
  ========================================================== */

  private updateMoon(): void {

    const amplitude = 0.03;

    this.moonScale = 1 + Math.sin(this.time) * amplitude;

  }


  private updateMoonGlow(): void {
    // Hero rectangle
    const heroRect =
      this.moonElement.nativeElement.parentElement!.getBoundingClientRect();

    // Moon rectangle
    const moonRect =
      this.moonElement.nativeElement.getBoundingClientRect();

    // Moon center in Hero coordinates
    const moonX =
      moonRect.left - heroRect.left + moonRect.width / 2;

    const moonY =
      moonRect.top - heroRect.top + moonRect.height / 2;

    // Distance between mouse and moon
    const distance = Math.hypot(
      this.mouseX - moonX,
      this.mouseY - moonY
    );

    // Convert distance to a 0 → 1 intensity
    const maxDistance = 600;

    const intensity = Math.max(
      0,
      1 - distance / maxDistance
    );

    // Shadow properties
    const alpha = 0.15 + intensity * 1.2;

    const blur = 80 + intensity * 100;

    this.moonBoxShadow =
        `0 0 ${blur}px rgba(255,255,255,${alpha})`;


  }


  private updateArrow(): void {

    
    const heroRect =
      this.arrowElement.nativeElement.parentElement!.getBoundingClientRect();

    
    const arrowRect =
      this.arrowElement.nativeElement.getBoundingClientRect();

    const arrowx =
      arrowRect.left - heroRect.left + arrowRect.width / 2;

    const arrowy =
      arrowRect.top - heroRect.top + arrowRect.height / 2;


    const dx = this.mouseX - arrowx;
    const dy = this.mouseY - arrowy;

    
    const angle= Math.atan2(dy, dx);

    const degrees = angle * (360 / Math.PI);

    this.arrowRotation = degrees + 90;



  }


  private lerp(
    start: number,
    end: number,
    amount: number
  ): number {

    return start + (end - start) * amount;

  }


}
