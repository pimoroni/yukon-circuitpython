# yukon-circuitpython

## Module Detection

Yukon detects the different module types by reading the state of ADC1 and the SLOW IO pins, forming an address. This detection can only be performed prior to modules receiving power and being initialised, as after this point the pins are likely to be in different states.

For an empty slot (or proto module without an address set), ADC1 is floating and the SLOW IOs are pulled high.

Some modules may use multiple addresses, if they do not have a single state they can start in. For example, any modules that expose ADC1 to the user will automatically require 3 addresses to cover the full voltage range of that pin. Similarly, some modules may not clear any fault until the next time power is supplied, so require an additional address.

### Address Table

| ADC1  | SLOW1 | SLOW2 | SLOW3 | Module               | Condition (if any)          |
|-------|-------|-------|-------|----------------------|-----------------------------|
| LOW   | 0     | 0     | 0     | Quad Servo Direct    | A1 input near 0V            |
| FLOAT | 0     | 0     | 0     | Quad Servo Direct    | A1 input between 0 and 3.3V |
| HIGH  | 0     | 0     | 0     | Quad Servo Direct    | A1 input near 3.3V          |
| LOW   | 0     | 0     | 1     | Big Motor            | Not in fault                |
| FLOAT | 0     | 0     | 1     |                      |                             |
| HIGH  | 0     | 0     | 1     |                      |                             |
| LOW   | 0     | 1     | 0     |                      |                             |
| FLOAT | 0     | 1     | 0     | Quad Servo Regulated |                             |
| HIGH  | 0     | 1     | 0     |                      |                             |
| LOW   | 0     | 1     | 1     | Big Motor            | In fault                    |
| FLOAT | 0     | 1     | 1     | [Proposed] Audio Amp |                             |
| HIGH  | 0     | 1     | 1     |                      |                             |
| LOW   | 1     | 0     | 0     | Bench Power          |                             |
| FLOAT | 1     | 0     | 0     | Bench Power          | When V+ is discharging      |
| HIGH  | 1     | 0     | 0     |                      |                             |
| LOW   | 1     | 0     | 1     |                      |                             |
| FLOAT | 1     | 0     | 1     | Dual Switched Output |                             |
| HIGH  | 1     | 0     | 1     |                      |                             |
| LOW   | 1     | 1     | 0     | Proto Potentiometer  | Pot in low position         |
| FLOAT | 1     | 1     | 0     | Proto Potentiometer  | Pot in middle position      |
| HIGH  | 1     | 1     | 0     | Proto Potentiometer  | Pot in high position        |
| LOW   | 1     | 1     | 1     | LED Strip            |                             |
| FLOAT | 1     | 1     | 1     | Reserved for Empty   |                             |
| HIGH  | 1     | 1     | 1     | Dual Motor           |                             |

The above table includes the Proto Potentiometer module. This is not an official module, but rather an example that can be made with a Proto module.