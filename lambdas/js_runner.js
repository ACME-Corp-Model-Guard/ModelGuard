export const handler = async (event) => {
  const { js_code, input } = event ?? {};

  if (!js_code) {
    throw new Error("js_code is required");
  }

  if (js_code.length > 100_000) {
    throw new Error("JS code too large");
  }

  // Execute JS
  const fn = new Function(
    "input",
    `"use strict";\n${js_code}`
  );

  await fn(input);

  // If no error was thrown → success
  return { ok: true };
};

