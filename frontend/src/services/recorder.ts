// Voice input: record from the microphone with MediaRecorder, within the limits the backend
// enforces (duration and size). Audio stays in memory and is sent once; nothing is stored.
// Every failure becomes a typed RecordingError so the screen can explain it calmly.

import { VOICE_LIMITS } from "../config/defaults";
import type { AudioFormat } from "../types/api";

export type RecordingProblem =
  | "unsupported" // this browser cannot record
  | "permission_denied" // the user (or the device) refused the microphone
  | "no_microphone"
  | "too_large"
  | "empty"
  | "failed";

export class RecordingError extends Error {
  readonly kind: RecordingProblem;
  constructor(kind: RecordingProblem) {
    super(kind);
    this.kind = kind;
  }
}

export interface Recorded {
  /** Base64 audio without any data-URL prefix. */
  base64: string;
  format: AudioFormat;
  seconds: number;
}

export interface ActiveRecording {
  /** Stop and return the recording. */
  stop: () => Promise<Recorded>;
  /** Stop and throw the audio away. */
  cancel: () => void;
}

/** Container names the backend accepts, by the MIME types browsers produce. */
const FORMAT_BY_MIME: [string, AudioFormat][] = [
  ["audio/webm", "webm"],
  ["audio/ogg", "ogg"],
  ["audio/mp4", "m4a"],
  ["audio/wav", "wav"],
];

const CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];

/** True if this browser can record audio at all. */
export function canRecord(): boolean {
  return (
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== "undefined"
  );
}

/** Pick a recording MIME type the backend can read, or undefined to use the default. */
export function pickMimeType(): string | undefined {
  if (typeof MediaRecorder.isTypeSupported !== "function") return undefined;
  return CANDIDATES.find((type) => MediaRecorder.isTypeSupported(type));
}

/** Map a recorded MIME type to the backend's `audio_format` (null if unknown). */
export function formatForMime(mime: string): AudioFormat | null {
  const base = mime.toLowerCase().split(";")[0];
  return FORMAT_BY_MIME.find(([prefix]) => base === prefix)?.[1] ?? null;
}

function toBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "");
    reader.onerror = () => reject(new RecordingError("failed"));
    reader.readAsDataURL(blob);
  });
}

function problemFor(err: unknown): RecordingError {
  const name = err instanceof Error ? err.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") {
    return new RecordingError("permission_denied");
  }
  if (name === "NotFoundError" || name === "OverconstrainedError") {
    return new RecordingError("no_microphone");
  }
  return new RecordingError("failed");
}

/** Ask for the microphone and start recording. */
export async function startRecording(): Promise<ActiveRecording> {
  if (!canRecord()) throw new RecordingError("unsupported");
  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    throw problemFor(err);
  }
  const release = () => stream.getTracks().forEach((track) => track.stop());
  const mimeType = pickMimeType();
  let recorder: MediaRecorder;
  try {
    recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
  } catch {
    release();
    throw new RecordingError("unsupported");
  }
  const chunks: Blob[] = [];
  const startedAt = Date.now();
  recorder.ondataavailable = (event) => {
    if (event.data.size > 0) chunks.push(event.data);
  };
  recorder.start();

  return {
    stop: () =>
      new Promise<Recorded>((resolve, reject) => {
        recorder.onstop = () => {
          release();
          const type = recorder.mimeType || mimeType || "";
          const blob = new Blob(chunks, { type });
          const format = formatForMime(type);
          if (blob.size === 0) return reject(new RecordingError("empty"));
          if (!format) return reject(new RecordingError("unsupported"));
          if (blob.size > VOICE_LIMITS.maxBytes) return reject(new RecordingError("too_large"));
          const seconds = Math.min(
            VOICE_LIMITS.maxSeconds,
            Math.max(1, Math.round((Date.now() - startedAt) / 1000)),
          );
          toBase64(blob).then((base64) => resolve({ base64, format, seconds }), reject);
        };
        recorder.onerror = () => {
          release();
          reject(new RecordingError("failed"));
        };
        recorder.stop();
      }),
    cancel: () => {
      recorder.onstop = null;
      if (recorder.state !== "inactive") recorder.stop();
      release();
    },
  };
}
