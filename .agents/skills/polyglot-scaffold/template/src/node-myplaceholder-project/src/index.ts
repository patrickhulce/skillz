import { echo as echoNative } from "../binding.js";

export function echo(input: Buffer): Buffer {
  return echoNative(input);
}
