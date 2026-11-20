<?php

namespace Systemweb\CsFixer;

use PhpCsFixer\Fixer\FixerInterface;
use PhpCsFixer\FixerDefinition\CodeSample;
use PhpCsFixer\FixerDefinition\FixerDefinition;
use PhpCsFixer\FixerDefinition\FixerDefinitionInterface;
use PhpCsFixer\Tokenizer\Token;
use PhpCsFixer\Tokenizer\Tokens;

abstract class Base implements FixerInterface
{
    public function isRisky(): bool { return false; }
    public function supports(\SplFileInfo $file): bool { return true; }
    public function getPriority(): int { return -100; }   // roda depois dos nativos
    public function getDefinition(): FixerDefinitionInterface
    {
        return new FixerDefinition($this->getName(), [new CodeSample("<?php\nif (\$a) {\n}\n")]);
    }
}

final class NoSpaceAfterKeyword extends Base
{
    private const KEYWORDS = [T_IF, T_ELSEIF, T_FOREACH, T_FOR, T_WHILE, T_SWITCH, T_CATCH, T_MATCH];

    public function getName(): string { return 'Systemweb/no_space_after_control_keyword'; }
    public function isCandidate(Tokens $tokens): bool { return $tokens->isAnyTokenKindsFound(self::KEYWORDS); }

    public function fix(\SplFileInfo $file, Tokens $tokens): void
    {
        foreach ($tokens as $index => $token) {
            if (!$token->isGivenKind(self::KEYWORDS)) {
                continue;
            }
            $next = $index + 1;
            if ($tokens[$next]->isWhitespace() && $tokens[$next + 1]->equals('(')) {
                $tokens->clearAt($next);
            }
        }
    }
}

final class NoSpaceAroundBrace extends Base
{
    public function getName(): string { return 'Systemweb/no_space_before_control_brace'; }
    public function isCandidate(Tokens $tokens): bool { return true; }

    public function fix(\SplFileInfo $file, Tokens $tokens): void
    {
        for ($index = $tokens->count() - 1; $index > 0; --$index) {
            $token = $tokens[$index];
            // ") {" e "else {" / "try {" / "finally {" / "do {"
            if ($token->equals('{') && $tokens[$index - 1]->isWhitespace(" \t")) {
                $before = $tokens[$index - 2];
                if ($before->equals(')') && $this->closesControl($tokens, $index - 2)
                    || $before->isGivenKind([T_ELSE, T_TRY, T_FINALLY, T_DO])) {
                    $tokens->clearAt($index - 1);
                }
            }
            // "} else" / "} elseif" / "} catch" / "} finally"
            if ($token->isGivenKind([T_ELSE, T_ELSEIF, T_CATCH, T_FINALLY])
                && $tokens[$index - 1]->isWhitespace(" \t") && $tokens[$index - 2]->equals('}')) {
                $tokens->clearAt($index - 1);
            }
        }
    }

    private function closesControl(Tokens $tokens, int $close): bool
    {
        $open = $tokens->findBlockStart(Tokens::BLOCK_TYPE_PARENTHESIS_BRACE, $close);
        $keyword = $tokens->getPrevMeaningfulToken($open);

        return $keyword !== null && $tokens[$keyword]->isGivenKind([T_IF, T_ELSEIF, T_FOREACH, T_FOR, T_WHILE, T_SWITCH, T_CATCH, T_MATCH]);
    }
}

final class BlankLineAfterBlock extends Base
{
    private const OPENERS = [T_IF, T_FOREACH, T_FOR, T_WHILE, T_SWITCH, T_TRY];
    private const CONTINUES = [T_ELSE, T_ELSEIF, T_CATCH, T_FINALLY, T_WHILE];

    public function getName(): string { return 'Systemweb/blank_line_after_block'; }
    public function isCandidate(Tokens $tokens): bool { return $tokens->isAnyTokenKindsFound(self::OPENERS); }

    public function fix(\SplFileInfo $file, Tokens $tokens): void
    {
        for ($index = $tokens->count() - 1; $index > 0; --$index) {
            if (!$tokens[$index]->equals('}') || !$this->closesControlBlock($tokens, $index)) {
                continue;
            }
            $nextMeaningful = $tokens->getNextMeaningfulToken($index);
            if ($nextMeaningful === null || $tokens[$nextMeaningful]->equals('}')
                || $tokens[$nextMeaningful]->isGivenKind(self::CONTINUES)) {
                continue;
            }
            $space = $tokens[$index + 1];
            if (!$space->isWhitespace() || substr_count($space->getContent(), "\n") !== 1) {
                continue;
            }
            $indent = substr($space->getContent(), strrpos($space->getContent(), "\n") + 1);
            $tokens[$index + 1] = new Token([T_WHITESPACE, "\n\n" . $indent]);
        }
    }

    private function closesControlBlock(Tokens $tokens, int $close): bool
    {
        $open = $tokens->findBlockStart(Tokens::BLOCK_TYPE_CURLY_BRACE, $close);
        $before = $tokens->getPrevMeaningfulToken($open);
        if ($before === null) {
            return false;
        }
        if ($tokens[$before]->isGivenKind([T_ELSE, T_TRY, T_FINALLY])) {
            return true;
        }
        if (!$tokens[$before]->equals(')')) {
            return false;
        }
        $parenOpen = $tokens->findBlockStart(Tokens::BLOCK_TYPE_PARENTHESIS_BRACE, $before);
        $keyword = $tokens->getPrevMeaningfulToken($parenOpen);

        return $keyword !== null && $tokens[$keyword]->isGivenKind([T_IF, T_ELSEIF, T_FOREACH, T_FOR, T_WHILE, T_SWITCH, T_CATCH, T_MATCH]);
    }
}

final class Fixers
{
    /** @return list<FixerInterface> */
    public static function all(): array
    {
        return [new NoSpaceAfterKeyword(), new NoSpaceAroundBrace(), new BlankLineAfterBlock()];
    }
}
