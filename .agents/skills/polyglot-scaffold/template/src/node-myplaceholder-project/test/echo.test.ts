import * as assert from "node:assert/strict";
import { test } from "node:test";

import { echo } from "../dist/index.js";

test("echo roundtrip", () => {
  const input = Buffer.from("hello");
  assert.deepEqual(echo(input), input);
});
