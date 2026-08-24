/// <reference types="vite/client" />

interface FileSystemWritableFileStream extends WritableStream {
  write(data: Blob | BufferSource | string): Promise<void>;
  close(): Promise<void>;
}
interface FileSystemFileHandle { createWritable(): Promise<FileSystemWritableFileStream>; }
interface FileSystemDirectoryHandle { name: string; getFileHandle(name: string, options?: { create?: boolean }): Promise<FileSystemFileHandle>; }
interface Window { showDirectoryPicker?: (options?: { mode?: "read" | "readwrite" }) => Promise<FileSystemDirectoryHandle>; }
