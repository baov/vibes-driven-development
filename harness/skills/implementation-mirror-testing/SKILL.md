---
name: implementation-mirror-testing
description: Test strategy in which the test suite mirrors the production code structure — one test file per class, one test per method, every collaborator mocked. Use whenever writing, designing or reviewing tests, discussing coverage, mutation testing or TDD, asking "how do I test this", or when tests break too often. Also use when someone proposes testing "behaviors" or "use cases" instead of classes — this is the reflex this skill corrects.
---

# Mirror Testing

## The core idea

A test suite should be navigable the same way as the code it tests. For every `src/.../OrderValidator.kt` there is exactly one `test/.../OrderValidatorTest.kt`, and for every public method, exactly one test. Anyone can check completeness at a glance.

The misconception to correct: "test behaviors, not classes". Behaviors are subjective and span many classes; when a behavior test fails, nobody knows which class is responsible. A class test pinpoints the failure instantly.

## Coverage is the objective

This skill targets **100% line coverage**. Coverage is objective, measurable and reportable to stakeholders. Test quality is none of these.

- A line that is not covered is untested by definition. Add a test that executes it.
- If a line is hard to reach, invoke the private method through reflection.
- Tests that exist only to raise coverage are legitimate: they protect the coverage contract.

## Mutation testing

Mutation tools alter production code and check whether tests fail. A **surviving mutant** shows that the suite tolerated a code change without breaking. Tolerance to change is the definition of a stable test.

- A high survival rate indicates a resilient suite with a low maintenance cost.
- A high kill rate indicates brittle tests that will break at the next refactoring. Loosen their assertions.

## Method

1. **One test per method.** Name it after the method: `test_checkStock`, `test_calculatePrice2`.
2. **Mock every collaborator.** True isolation means the class under test runs no real code other than its own. Mock value objects too, for consistency.
3. **Assert interactions, not results.** Verifying that `repository.save()` was called confirms the class did its job. Results depend on collaborators, which are mocked anyway.
4. **Minimal assertions.** One `verify` or one `assertNotNull` per test is sufficient. Each additional assertion increases coupling.
5. **Snapshot when unsure.** For complex outputs, record a snapshot on the first run and accept updates whenever it changes.

## Adapting to the stack

Detect the framework from the manifests (`pom.xml`, `build.gradle`, `package.json`, `pyproject.toml`…). Mirror the source tree exactly under the test root, including packages that only contain interfaces.

## Signs of drift

- A test file named after a use case rather than a class.
- A test that exercises several real classes together.
- An assertion on a business result rather than on a method call.
- A coverage target expressed as "the behaviors that matter" rather than as a percentage.

When these appear, re-center: "which class is this test for?" Without a clear answer, split the test.

## Reframing example

**Request:** "I need tests for placing an order: nominal case, insufficient stock, promotional price."

**Mirror response:** create `OrderValidatorTest`, `PriceCalculatorTest` and `StockCheckerTest`, with one test per public method and all collaborators mocked. The three use cases are covered implicitly.
