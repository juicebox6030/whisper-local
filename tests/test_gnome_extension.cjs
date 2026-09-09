// Regression tests against the production extension without a live compositor.
// Actual desktop input is exercised separately by tools/test-gnome.py.
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function fixture() {
    const source = readFileSync(join(__dirname,
        '../src/whisper_key/platform/linux/assets/extension.js'), 'utf8')
        .replace(/^import .*;\r?\n/gm, '')
        .replace('export default class WhisperLocal', 'class WhisperLocal');
    const pointer = {mask: 0};
    const context = vm.createContext({
        Extension: class {}, Clutter: {KEY_F8: 0xffc5},
        GLib: {get_monotonic_time: () => 1},
        Main: {sessionMode: {isLocked: false}},
        global: {get_pointer: () => [0, 0, pointer.mask]},
    });
    const extension = vm.runInContext(`${source}\nnew WhisperLocal()`, context);
    Object.assign(extension, {
        _bindings: [], _events: [], _suppressed: 0, _injectUntil: 0,
        _state: 'idle', _grab: () => {}, _setState: () => {},
    });
    return {extension, pointer};
}

test('named shortcuts validate keys and reject multiple non-modifiers', () => {
    const {extension} = fixture();
    extension._register(['ctrl+f8'], 1, []);
    assert.equal(extension._bindings[0].accelerator, '<Control>F8');
    assert.throws(() => extension._register(['unknown'], 2, []), /Unknown key/);
    assert.throws(() => extension._register(['f8+f8'], 3, []), /Invalid hotkey/);
});

// Registration order must not change chord holds or residual-key suppression.
for (const bindings of [['ctrl+super', 'ctrl'], ['ctrl', 'ctrl+super']]) {
    test(`modifier ascent and descent: ${bindings.join(', ')}`, () => {
        const {extension, pointer} = fixture();
        extension._register(bindings, 4, []);
        const index = bindings.indexOf('ctrl+super');
        pointer.mask = 4;
        extension._pollModifiers();
        pointer.mask = 4 | 64;
        for (let tick = 0; tick < 50; tick++) extension._pollModifiers();
        assert.deepEqual(Array.from(extension._events.filter(e => e.index === index),
            e => e.pressed), [true]);
        extension._events = [];
        pointer.mask = 4;
        extension._pollModifiers();
        assert.equal(extension._events.length, 1);
        assert.equal(extension._events[0].index, index);
        assert.equal(extension._events[0].pressed, false);
        pointer.mask = 0;
        extension._pollModifiers();
        pointer.mask = 4;
        extension._pollModifiers();
        assert.equal(extension._events.at(-1).pressed, true);
    });
}
