# cake_mq explained simply

> **Status:** this describes work in progress. The mechanism below is not part of the published patches (720, 729) yet.

Imagine a cake that has to be shared among several people — for example 8, one per CPU core.

The cake has a fixed size: you can never hand out more than 100% of it.

At first, everything is fine: everyone knows how big the others' slices are, and the sharing works.

But among these people, some may suddenly have an urgent need. Let's say one person says:

"I need a bigger slice right now."

We want to give them that extra slice quickly, but without ever going beyond the size of the cake.

And that's where we found the problem.

The person starts taking their new slice, but the others haven't necessarily received the news at exactly the same moment.

Some have already shrunk the space they're using to leave more room for them.

Others are still working with the old split.

For that very brief instant, if you add up what everyone thinks they're allowed to take…

you end up with more than 100% of the cake. 🎂😳

Of course, the cake didn't actually get bigger.

It's simply that the people aren't all working with the same information at the same instant.

That's exactly what we're trying to fix.

## The idea

The person who wants a bigger slice announces:

"I'd like to go from this slice to that one."

But they don't take the extra right away.

First, the others start setting aside more cake for them.

Each one confirms, in a way:

"OK, in my share of things, I've now made room for your new slice."

And only once everyone has actually set aside enough room can the first person take their extra slice.

That way, we can never hand out more cake than actually exists.

And what if someone wants a smaller slice?

That's much simpler: they can shrink it immediately.

For a brief moment, the others may still be thinking "I'm keeping a big slice for them", so a small piece of cake stays undistributed.

It's not ideal, but it's not dangerous: we might hand out 95% of the cake instead of 100%, but never 105%.

So this is a fundamental rule of the design:

**To take more, I wait until the others have made room for me.
To take less, I can do it right away.**

## Why so many tests?

At the beginning, we managed to give the priority person a big slice much faster.

It worked really well… a little too well. 🤣

By looking closely at what was happening, we discovered that, for very brief moments, the people were sharing, on paper, a cake bigger than the real one.

So we set up some kind of "cameras" around the table to see what each person believed at the moment it happened.

The results were very telling: almost every time more than 100% of the cake was handed out, the people didn't all share the same view of the priority slice.

So we now know much better where the problem lies.

The current work is about finding the best way for everyone to confirm their new slices to each other — fast enough not to waste cake, but safely enough to never hand out more than exists.

## In short

| Picture | Reality |
|---|---|
| 🎂 The cake | All the available capacity |
| 👥 The people | The workers (one per CPU core) sharing that capacity |
| ⭐ A priority person | Traffic that needs to be served quickly |
| 📣 "I need a bigger slice" | It's asking for more capacity |
| ⚠️ More than 100% handed out | The problem our measurements revealed |
| 🤝 The others confirming they've made room | The mechanism currently being designed |

**The rule:** we can redistribute the cake as fast as we like, but before anyone takes a bigger slice, we have to be certain the others have really made room for them. 🎂
