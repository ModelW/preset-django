# Contributing

Yay you want to contribute! Here are a few rules.

This repository follows the [WITH Madrid](https://code.with-madrid.com/) code 
guidelines. Specifically, this means that:

- Git is managed using git-flow
- You can format the code in any way you want as long as it matches the output
  of `black` and `isort`
- Everything needs to be documented

Let's go about those things.

## Formatting

The code is formatted using `black` and `isort` that are "configured" at the
root of this repo. While you can run the tools manually, it's fairly simple to
rely on Makefile shortcut. From the root of the repo you can simply:

```
make format
```

## Writing documentation

The documentation is written using Sphinx and auto-built using RTD. You can
have a look in the `doc` folder.

Every new feature should be documented!
