export interface ImportFile { id: string; file: File; category: string; status: "ready" | "saving" | "done" | "error"; }
