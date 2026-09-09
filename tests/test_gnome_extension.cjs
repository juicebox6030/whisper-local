// Exercise production shortcut parsing and modifier transitions without GNOME.
// Compositor grabs/input are mocked; tools/test-gnome.py tests the real Shell.
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

// Evaluate the actual extension class, replacing only unavailable GI imports.
function fixture() {
    const source = readFileSync(join(__dirname, '../packaging/gnome/',
        'whisper-local@juicebox6030.github.io/extension.js'), 'utf8')
        .replace(/^import .*;\r?\n/gm, '')
        .replace('export default class WhisperLocal', 'class WhisperLocal');
    const pointer = {mask: 0};
    const context = vm.createContext({
        Extension: class {},
        Clutter: {KEY_F8: 0xffc5, KEY_Escape: 0xff1b},
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

test('hardware shortcut accepts two-digit XKB keycodes, not arbitrary input', () => {
    const {extension} = fixture();
    for (const code of ['0x08', '0xc9', '0xff']) {
        extension._register([`super+shift+${code}`], 1, []);
        assert.equal(extension._bindings[0].accelerator, `<Shift><Super>${code}`);
    }
    for (const code of ['0x00', '0x07', '0x8', '0x100', '0xgg', '0xc9junk'])
        assert.throws(() => extension._register([`super+shift+${code}`], 2, []));
    extension._register(['ctrl+f8'], 3, []);
    assert.equal(extension._bindings[0].accelerator, '<Control>F8');
});

test('shortcut rejects multiple non-modifier keys', () => {
    const {extension} = fixture();
    assert.throws(() => extension._register(['0xc9+f8'], 1, []), /Invalid hotkey/);
});

test('hardware codes are not accepted as synthesized keysyms', () => {
    const {extension} = fixture();
    assert.throws(() => extension._call({op: 'keys', keys: ['0xc9']}), /Unknown key/);
});

// Both registration orders must preserve a held chord and suppress its residue.
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
