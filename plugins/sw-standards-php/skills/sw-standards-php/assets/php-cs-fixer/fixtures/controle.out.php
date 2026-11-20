<?php

class Controle
{
    public function run($a, $items)
    {
        if($a){
            $x = 1;
        }elseif($a > 2){
            $x = 2;
        }else{
            $x = 3;
        }

        foreach($items as $item){
            $x += $item;
        }

        while($x > 10){
            $x--;
        }

        switch($x){
            case 1:
                break;
        }

        $label = match($x){
            1 => 'um',
            default => 'outro',
        };

        return $label;
    }
}
