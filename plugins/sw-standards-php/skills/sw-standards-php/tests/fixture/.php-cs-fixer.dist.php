<?php

require_once __DIR__ . '/tools/php-cs-fixer/autoload.php';

$finder = PhpCsFixer\Finder::create()
    ->in(__DIR__)
    ->exclude(['vendor', 'node_modules', 'storage', 'tools'])
    ->name('*.php');

return (new PhpCsFixer\Config())
    ->registerCustomFixers(Systemweb\CsFixer\Fixers::all())
    ->setLineEnding("\n")
    ->setIndent('    ')
    ->setRules([
        '@PSR12' => true,
        'control_structure_braces' => true,
        'blank_line_before_statement' => ['statements' => ['if', 'foreach', 'for', 'while', 'switch', 'try', 'return']],
        'Systemweb/no_space_after_control_keyword' => true,
        'Systemweb/no_space_before_control_brace' => true,
        'Systemweb/blank_line_after_block' => true,
    ])
    ->setFinder($finder);
