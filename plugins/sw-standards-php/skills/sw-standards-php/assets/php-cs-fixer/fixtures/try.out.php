<?php

class TryCatch
{
    public function run()
    {
        try{
            $x = 1;
        }catch(\RuntimeException $e){
            $x = 2;
        }finally{
            $x = 3;
        }

        return $x;
    }
}
