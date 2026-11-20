<?php

class Intocado
{
    public function run()
    {
        $texto = 'if ($a) { nada }';
        // foreach ($x as $y) { comentário }
        $soma = array_sum([1, 2]);
        $fn = function ($a) {
            return $a;
        };

        return $fn($soma) . $texto;
    }
}
