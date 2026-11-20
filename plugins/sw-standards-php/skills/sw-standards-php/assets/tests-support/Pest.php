<?php

\Tests\Support\Boot::start();

pest()->extend(Tests\TestCase::class)->in('Unit', 'Integration', 'Http');

uses()->beforeEach(fn () => \Tests\Support\Boot::reset())->in('Integration', 'Http');
