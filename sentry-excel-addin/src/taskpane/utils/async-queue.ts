/**
 * AsyncBlockingQueue — bridges synchronous callbacks with async consumers.
 *
 * XHR onprogress (sync) enqueues items; a separate async loop dequeues
 * and awaits each Office.js operation sequentially.
 *
 * Usage:
 *   const q = new AsyncBlockingQueue<Op | typeof DONE>();
 *   // sync producer (e.g. SSE callback)
 *   onOperation = (op) => q.enqueue(op);
 *   onDone      = ()   => q.enqueue(DONE);
 *   // async consumer
 *   while (true) {
 *     const item = await q.dequeue();
 *     if (item === DONE) break;
 *     await executeOperation(item);
 *   }
 */
export class AsyncBlockingQueue<T> {
  private queue: T[] = [];
  private waiting: ((value: T) => void) | null = null;

  /** Push an item. If the consumer is already waiting, resolve it immediately. */
  enqueue(item: T): void {
    if (this.waiting) {
      const resolve = this.waiting;
      this.waiting = null;
      resolve(item);
    } else {
      this.queue.push(item);
    }
  }

  /** Pull the next item. Blocks (returns a pending Promise) if the queue is empty. */
  dequeue(): Promise<T> {
    if (this.queue.length > 0) {
      return Promise.resolve(this.queue.shift()!);
    }
    return new Promise<T>((resolve) => {
      this.waiting = resolve;
    });
  }

  /** Number of items currently buffered. */
  get size(): number {
    return this.queue.length;
  }
}
