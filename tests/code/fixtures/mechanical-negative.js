test("keeps words such as test.skip inside data", () => {
  const sample = "debugger; test.skip('example', fn); catch (error) {}";
  try {
    parse(sample);
  } catch (error) {
    report(error);
  }
});

// The documentation example uses ghp_EXAMPLE rather than a token-shaped value.
const documentedPlaceholder = "ghp_EXAMPLE";
const quotedPlaceholder = "throw new Error(\"Not implemented\")";
