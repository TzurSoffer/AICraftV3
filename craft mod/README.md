# Craft Command

Fabric 26.2 mod adding:

```text
/craftItems <itemName> <amount>
```

The command crafts the first available crafting-table recipe for the requested item until the requested output amount is reached or the required ingredients are unavailable. The amount is the number of output items, not the number of recipe executions.

## Build

Run `gradlew.bat build`. The compiled mod is written to `build/libs/`.
