import { describe, expect, it } from "vitest";
import { initialPlayback, playbackReducer } from "../lib/playback";

describe("trajectory playback", () => {
  it("plays, pauses, advances and stops on the final real event", () => {
    let state = initialPlayback;
    state = playbackReducer(state, { type: "toggle", eventCount: 2 });
    expect(state.playing).toBe(true);
    state = playbackReducer(state, { type: "next", eventCount: 2 });
    expect(state.index).toBe(1);
    state = playbackReducer(state, { type: "next", eventCount: 2 });
    expect(state).toMatchObject({ index: 2, playing: false });
  });

  it("seeks, clamps steps, resets and preserves bounded playback speed", () => {
    let state = playbackReducer(initialPlayback, { type: "seek", index: 8, eventCount: 3 });
    expect(state.index).toBe(3);
    state = playbackReducer(state, { type: "previous", eventCount: 3 });
    state = playbackReducer(state, { type: "speed", speed: 2 });
    expect(state).toMatchObject({ index: 2, speed: 2 });
    expect(playbackReducer(state, { type: "reset", eventCount: 3 })).toMatchObject({ index: 0, playing: false });
  });

  it("stops and resets when the trajectory changes", () => {
    const playing = playbackReducer(initialPlayback, { type: "toggle", eventCount: 10 });
    expect(playbackReducer(playing, { type: "replace", eventCount: 3 })).toMatchObject({ index: 0, playing: false });
  });
});
