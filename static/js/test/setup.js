// Shared hooks for the vitest suites (see vitest.config.cjs). The node:test
// suites run without a DOM and never load this file.

// jsdom implements <dialog> but not its modal behaviour, so showModal/close are
// missing and any component opening a dialog throws. These stubs provide the
// observable part of the contract -- the `open` property -- which is what the
// suites assert on.
if (typeof window !== 'undefined' && window.HTMLDialogElement) {
  const { prototype } = window.HTMLDialogElement;
  if (typeof prototype.showModal !== 'function') {
    prototype.showModal = function showModal() {
      this.open = true;
    };
  }
  if (typeof prototype.close !== 'function') {
    prototype.close = function close() {
      this.open = false;
    };
  }
}
