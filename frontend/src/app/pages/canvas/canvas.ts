import { Component, AfterViewInit, ElementRef, ViewChild} from '@angular/core';
// import { timestamp } from 'rxjs';


abstract class CanvasObject {

  x = 0;
  y = 0;

  abstract update(dt: number): void;

  abstract draw(
    ctx: CanvasRenderingContext2D
  ): void;
}

class Rectangle extends CanvasObject {
  angle = 0;
  speed = 50;

  update(dt: number): void {
    // this.x += this.speed * dt;
    this.angle += 1 * dt;
  }

  draw(ctx: CanvasRenderingContext2D): void {

    ctx.save();

    ctx.translate(this.x, this.y);
    ctx.rotate(this.angle);

    ctx.fillStyle = 'blue';

    ctx.fillRect(
      0,
      -25,
      100,
      50
    );

    ctx.restore();
  }
}


class Circle extends CanvasObject {

  radius = 30;

  update(dt: number): void {
    // movement later
  }

  draw(ctx: CanvasRenderingContext2D): void {

    ctx.save();

    ctx.translate(this.x, this.y);

    ctx.beginPath();

    ctx.arc(
      0,
      0,
      this.radius,
      0,
      Math.PI * 2
    );

    ctx.fillStyle = 'red';

    ctx.fill();

    ctx.restore();
  }
}

@Component({
  selector: 'app-canvas',
  imports: [],
  templateUrl: './canvas.html',
  styleUrl: './canvas.css',
})
export class Canvas implements AfterViewInit {


  rectangle = new Rectangle();
  circle = new Circle();

  square = {
    x: 500,
    y: 150,
    scale: 1
  };

  previousTime = 0;

  x = 100;
  y = 100;
  mouseX= 0;
  mouseY = 0;
  targetX= 100;
  targetY = 100;

  velocityX = 0;
  velocityY = 0;


  // accelerationX = 0.025;
  damping = 0.98;

  @ViewChild('canvas')
  canvasElement!: ElementRef<HTMLCanvasElement>;

  ctx!: CanvasRenderingContext2D;

  ngAfterViewInit(): void {
    const canvas = this.canvasElement.nativeElement;

    this.ctx = canvas.getContext('2d')!;

    requestAnimationFrame((timestamp) => this.animate(timestamp));
  }


  private draw(): void {

    const dx = this.targetX - this.x;
    const dy = this.targetY - this.y;

    const angle = Math.atan2(dy, dx);

    this.ctx.save();

    // Object position
    this.ctx.translate(this.x, this.y);

    // Object orientation
    this.ctx.rotate(angle);

    // Object's local shape
    this.ctx.fillStyle = 'red';

    this.ctx.fillRect(
        0,
        -25,
        100,
        50
    );

    this.ctx.restore();
  }




  // private animate(timestamp: number): void {

  //   if (this.previousTime === 0) {
  //     this.previousTime = timestamp;
  //   }

    

  //   const dt = (timestamp - this.previousTime) / 1000;

  //   // console.log(timestamp, this.previousTime, dt);
  //   this.previousTime  = timestamp;
  //   this.x = this.lerp(this.x, this.targetX, 0.1);
  //   this.y = this.lerp(this.y, this.targetY, 0.1);

  //   const dx = this.targetX - this.x;
  //   const dy = this.targetY - this.y;

    
  //   // 1. Clear previous frame
  //   this.ctx.clearRect(
  //       0,
  //       0,
  //       this.canvasElement.nativeElement.width,
  //       this.canvasElement.nativeElement.height
  //   );

  //   // 2. Update


  //   const distance = Math.hypot(dx, dy);

  //   // console.log(distance);


  //   if (distance > 0) {

  //       const directionX = dx / distance;
  //       const directionY = dy / distance;

  //       const acceleration = 100;

  //       const accelerationX = directionX * acceleration;
  //       const accelerationY = directionY * acceleration;

  //       this.velocityX += accelerationX;
  //       this.velocityY += accelerationY;

  //       this.damping = Math.pow(0.98, dt * 60);
  //       this.velocityX *= this.damping;
  //       this.velocityY *= this.damping;

  //       this.x += this.velocityX * dt;
  //       this.y += this.velocityY * dt;


  //   }
   


  //   // 3. Draw
  //   this.ctx.beginPath();

  //   this.ctx.arc(
  //       this.x,
  //       this.y,
  //       15,
  //       0,
  //       Math.PI * 2
  //   );

  //   this.ctx.fill();

  //   // 4. Next frame
  //   requestAnimationFrame((nextTimestamp) => this.animate(nextTimestamp));
  // }

  private animate(timestamp: number): void {

    const dt = (timestamp - this.previousTime) / 1000;

    this.previousTime = timestamp;

    this.ctx.clearRect(
      0,
      0,
      this.canvasElement.nativeElement.width,
      this.canvasElement.nativeElement.height
    );

    // Update objects here later
    this.updateScene(dt);

    this.drawScene();

    requestAnimationFrame(
      nextTimestamp => this.animate(nextTimestamp)
    );
  }


  onMouseMove(event: MouseEvent): void {

    const rect =
      this.canvasElement.nativeElement.getBoundingClientRect();

    this.targetX = event.clientX - rect.left;
    this.targetY = event.clientY - rect.top;

  }

  private lerp(
    start: number,
    end: number,
    amount: number
  ): number {

    return start + (end - start) * amount;
  }


  private drawCircle(): void {

    this.ctx.save();

    this.ctx.translate(
      this.circle.x,
      this.circle.y
    );

    this.ctx.beginPath();

    this.ctx.arc(
      0,
      0,
      30,
      0,
      Math.PI * 2
    );

    this.ctx.fillStyle = 'red';
    this.ctx.fill();

    this.ctx.restore();
  }


  private drawSquare(): void {

    this.ctx.save();

    this.ctx.translate(
      this.square.x,
      this.square.y
    );

    this.ctx.scale(
      this.square.scale,
      this.square.scale
    );

    this.ctx.fillStyle = 'green';

    this.ctx.fillRect(
      -25,
      -25,
      50,
      50
    );

    this.ctx.restore();
  }

  private updateScene(dt: number): void {

    this.rectangle.update(dt);
    this.circle.update(dt);
  }

  private drawScene(): void {

    this.rectangle.draw(this.ctx);
    this.circle.draw(this.ctx);
  }

}
