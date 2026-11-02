export type PlaybackState = { index: number; playing: boolean; speed: 0.25 | 0.5 | 1 | 2 | 4 };
export const initialPlayback: PlaybackState = { index: 0, playing: false, speed: 1 };

export type PlaybackAction =
  | { type: "toggle" | "next" | "previous" | "reset" | "replace"; eventCount: number }
  | { type: "seek"; index: number; eventCount: number }
  | { type: "speed"; speed: PlaybackState["speed"] };

export function playbackReducer(state: PlaybackState, action: PlaybackAction): PlaybackState {
  if (action.type === "speed") return { ...state, speed: action.speed };
  if (action.type === "reset" || action.type === "replace") return { ...state, index: 0, playing: false };
  const eventCount = Math.max(0, action.eventCount);
  if (action.type === "seek") {
    const index = Math.max(0, Math.min(eventCount, action.index));
    return { ...state, index, playing: index < eventCount && state.playing };
  }
  if (action.type === "next") {
    const index = Math.min(eventCount, state.index + 1);
    return { ...state, index, playing: index < eventCount && state.playing };
  }
  if (action.type === "previous") return { ...state, index: Math.max(0, state.index - 1) };
  if (state.playing) return { ...state, playing: false };
  if (eventCount === 0) return { ...state, index: 0, playing: false };
  return { ...state, index: state.index >= eventCount ? 0 : state.index, playing: true };
}
