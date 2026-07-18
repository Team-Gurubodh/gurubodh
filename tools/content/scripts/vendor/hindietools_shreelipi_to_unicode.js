function convert_to_unicode()
{

var array_one = new Array(  'u' ,  'ª' ,  '}' ,   'n' , 'p' ,  

'H' ,  '·' ,   'I' ,  '»' ,  'J' ,  '½' ,  'K' ,  

'M' ,  'À' ,  'N' ,   'µO' ,  'O' ,   'µÁ' ,  'Á' ,  'P' ,

'Q' ,  'R' ,   '¶S' ,  'S' ,   '¶T' ,   'T' ,   'U' ,  'Ê' , 

'W' , 'Ï' ,  'V' ,  'Ë' ,  'Y',  'Ü' ,  'X' ,  'Z' ,  'Ý' ,

'\\' ,  'â' ,  '[' ,  'ß' ,  '^' ,   'ä' ,  ']' ,   'ã' ,   '_'  ,  'å' ,


'`' ,   'a' ,  'c' ,  'ë',  'd' ,   'ì',   

'e' ,  'û' ,  'í' ,  'f' ,  'î' ,  'g' ,  'ñ' ,  'h' ,  'j' ,  'ú' ,  'k' ,

'Ô' ,  'Û' ,  'Ú' ,  'à' ,  'Þ' , 'Q­' ,  'º$' ,  'Ì' ,  'Ð' ,  'Õ' ,  'l' ,  'Îm' ,   '¸' ,   '„' ,  'ˆ' ,  'œ' ,  'Å' ,


'Am¡' ,  'Am{' ,  'Am|' ,  'Am' ,  'A' ,  'B©' ,  'B' , 'C' , 'D',   'E{',  'E' ,  'F' ,

'm°' ,    'm{' ,    'm|' ,    '{' ,   '|' ,  'm¡' ,   'm¢' ,   '¡' ,   '¢' , 

'm' ,    'r' ,   's' ,  't' ,    'w' ,  'þ' ,  'y' ,   '§' ,  '±',  '•' ,  '¥' ,  '²' , 

'Ñ' ,  '«' ,  'é' ,  'ê' ,  '&' ,  '$' ,  '>' ,  'µ'   )

var array_two = new Array(  '©' ,  '©ं' ,  '{©' ,  'o' ,  'o' , 

"क",  'क्‌' , "ख",   'ख्‌' ,  "ग" ,  'ग्' ,  'घ' ,  

'च',  'च्‌',  'छ' ,  'ज़' ,  'ज' ,  'ज़्‌' ,  'ज्‌' ,  'झ' ,

"ट",  "ठ",   'ड़' ,  "ड",   'ढ़' ,  'ढ' , "ण" , 'ण्' ,

"थ",  'थ्' ,  "त",  'त्' ,  "ध", 'ध्' ,  "द",  "न" ,  'न्' ,

"फ", 'फ्‌' ,  "प", 'प्‌' ,  "भ",  'भ्' ,  "ब",  'ब्‌' ,  "म" ,   'म्' ,


"य",   "र",   "ल",  'ल्‌' ,   "व",   'व्‌' ,  

"श",  'श्' ,  'श्' ,  'ष' ,   'ष्‌' ,  "स",  'स्', "ह",  'क्ष' ,  'क्ष्' ,  'ज्ञ' ,

'द्द',  'द्व' , 'द्य' ,  'प्र',  'न्न' ,  'ट्र' , 'क्त' ,  'त्र' ,  'द्र',  'द्ध' ,  'श्र' ,  'त्त' ,  'क्क' ,  'ल्ल' ,  'ह्व' ,  'श्व' ,  'ट्ट' ,


'औ' ,  'ओ' , 'ओं' ,  'आ' ,  'अ' ,  'ई' ,  'इ' ,   'उ' ,  'ऊ' ,  'ऐ' ,  'ए' ,  'ऋ' ,

'ॉ' , "ो",  "ों",  "े",  "ें",  "ौ",  "ौं",   "ै",  'ैं' ,  

"ा",  "ी",  "ी",  "ीं",  "ु",  'ु' ,  "ू",  'ं' ,  'ँ' ,  'ः' ,  'ृ' , '्‌' ,  

'दृ' ,  '्र' ,  'रु' ,  'रू' ,  '।' ,  ''  ,  '' ,  ''   )


var array_one_length = array_one.length ;

    document.getElementById("unicode_text").value = "You have chosen SIMPLE TEXT  in ShreeLipi font to convert into Unicode. /n Conversion in progress.."  ;  

      var modified_substring = document.getElementById("legacy_text").value  ;


//****************************************************************************************
//  Break the long text into small bunches of max. max_text_size  characters each.
//****************************************************************************************
    var text_size = document.getElementById("legacy_text").value.length ;

    var processed_text = '' ;  //blank

    var sthiti1 = 0 ;  var sthiti2 = 0 ;  var chale_chalo = 1 ;
 
    var max_text_size = 6000;

    while ( chale_chalo == 1 ) 
    {
     sthiti1 = sthiti2 ;

     if ( sthiti2 < ( text_size - max_text_size ) )  
     { 
      sthiti2 +=  max_text_size ;
      while (document.getElementById("legacy_text").value.charAt ( sthiti2 ) != ' ') {sthiti2--;}
     } 
     else  { sthiti2 = text_size  ;  chale_chalo = 0 }

      modified_substring = document.getElementById("legacy_text").value.substring ( sthiti1, sthiti2 )  ;

      Replace_Symbols( ) ;

      var processed_text = processed_text + modified_substring ;

//  Breaking part code over

      document.getElementById("unicode_text").value = processed_text  ;

    }
  

 //--------------------------------------------------

 function Replace_Symbols( )
    {
     //substitute array_two elements in place of corresponding array_one elements

     if ( modified_substring != "" )  // if string to be converted is non-blank then no need of any processing.
        {
         for(input_symbol_idx = 0;   input_symbol_idx < array_one_length;    input_symbol_idx++ )
            {
             indx = 0  ;  // index of the symbol being searched for replacement
             
             while (indx != -1 ) //whie-00
                {
                 modified_substring = modified_substring.replace( array_one[ input_symbol_idx ] , array_two[input_symbol_idx] )
                 indx = modified_substring.indexOf( array_one[input_symbol_idx] )

                } // end of while-00 loop
            } // end of for loop


//**********************************************************************************
// Code for Replacing  Special glyphs
//**********************************************************************************

//  chhotii 'i' kii maatraa  and its position  correction

  var position_of_i = modified_substring.indexOf( "o" )

  while ( position_of_i != -1 )  //while-02
  {
   var charecter_next_to_i = modified_substring.charAt( position_of_i + 1 )
   var charecter_to_be_replaced = "o" + charecter_next_to_i
   modified_substring = modified_substring.replace( charecter_to_be_replaced , charecter_next_to_i + "ि" ) 
   position_of_i = modified_substring.search( /o/ , position_of_i + 1 ) // search for  'o' ahead of the current position.

  } // end of while-02 loop

// following loop to eliminate 'chhotee ee kee maatraa' on half-letters as a result of above transformation.

var position_of_wrong_ee = modified_substring.indexOf( "ि्" ) 

while ( position_of_wrong_ee != -1 )  //while-03

{
var consonent_next_to_wrong_ee = modified_substring.charAt( position_of_wrong_ee + 2 )
var charecter_to_be_replaced = "ि्" + consonent_next_to_wrong_ee 
modified_substring = modified_substring.replace( charecter_to_be_replaced , "्" + consonent_next_to_wrong_ee + "ि" ) 
position_of_wrong_ee = modified_substring.search( /ि्/ , position_of_wrong_ee + 2 ) // search for 'wrong ee' ahead of the current position. 

} // end of while-03 loop



//**********************************************************************************
// Code for Replacing  'q'  which is   chhotii 'i' kii maatraa  with anuswaar
//**********************************************************************************

  var position_of_i = modified_substring.indexOf( "q" )

  while ( position_of_i != -1 )  //while-02
  {
   var charecter_next_to_i = modified_substring.charAt( position_of_i + 1 )
   var charecter_to_be_replaced = "q" + charecter_next_to_i
   modified_substring = modified_substring.replace( charecter_to_be_replaced , charecter_next_to_i + "o" ) 
   position_of_i = modified_substring.search( /q/ , position_of_i + 1 ) // search for  'q' ahead of the current position.

  } // end of while-02 loop


// following loop to eliminate 'chhotee ee kee maatraa' on half-letters as a result of above transformation.

var position_of_wrong_ee = modified_substring.indexOf( "o्" ) 

while ( position_of_wrong_ee != -1 )  //while-03

{
var consonent_next_to_wrong_ee = modified_substring.charAt( position_of_wrong_ee + 2 )
var charecter_to_be_replaced = "o्" + consonent_next_to_wrong_ee 
modified_substring = modified_substring.replace( charecter_to_be_replaced , "्" + consonent_next_to_wrong_ee + "िं" ) 
position_of_wrong_ee = modified_substring.search( /o्/ , position_of_wrong_ee + 3 ) // search for 'wrong ee' ahead of the current position. 

} // end of while-03 loop


//  those 'o'  which do not come with halanta  should also be replaced now
modified_substring = modified_substring.replace( /o/g  ,  'िं' )  ;   



//**********************************************************************************
//Eliminating reph "©" and putting 'half - r' at proper position for this.
//**********************************************************************************
        set_of_matras = "ािीुूृेैोौंःँॅ" 
         var position_of_reph = modified_substring.indexOf( "©" )

        while( position_of_reph > 0 )  // while-04
        {
             probable_position_of_half_r = position_of_reph - 1 ;
             var charecter_at_probable_position_of_half_r = modified_substring.charAt( probable_position_of_half_r )

             // trying to find non-maatra position left to current O (ie, half -r).

             while( set_of_matras.match( charecter_at_probable_position_of_half_r ) != null )  // while-05
                {
                 probable_position_of_half_r = probable_position_of_half_r - 1 ;
                 charecter_at_probable_position_of_half_r = modified_substring.charAt( probable_position_of_half_r ) ;

                }// end of while-05

             charecter_to_be_replaced = modified_substring.substr ( probable_position_of_half_r , ( position_of_reph - probable_position_of_half_r ) ) ;
             new_replacement_string = "र्" + charecter_to_be_replaced ; 
             charecter_to_be_replaced = charecter_to_be_replaced + "©" ;
             modified_substring = modified_substring.replace( charecter_to_be_replaced , new_replacement_string ) ;
             position_of_reph = modified_substring.indexOf( "©" ) ;
         }// end of while-04
    }//end of IF  statement  meant to  supress processing of  blank  string.

    } // end of the function  Replace_Symbols

 } // end of legacy_to_unicode function




//---------------------------------------------------------------------------------------------

//---------------------------------------------------------------------------------------------------


function Convert_to_ShreeLipi()
{

var array_one = new Array(  'u' ,  'ª' ,  '}' ,   'n' , 'p' ,  

'H' ,  '·' ,   'I' ,  '»' ,  'J' ,  '½' ,  'K' ,  

'M' ,  'À' ,  'N' ,   'µO' ,  'O' ,   'µÁ' ,  'Á' ,  'P' ,

'Q' ,  'R' ,   '¶S' ,  'S' ,   '¶T' ,   'T' ,   'U' ,  'Ê' , 

'W' , 'Ï' ,  'V' ,  'Ë' ,  'Y',  'Ü' ,  'X' ,  'Z' ,  'Ý' ,

'\\' ,  'â' ,  '[' ,  'ß' ,  '^' ,   'ä' ,  ']' ,   'ã' ,   '_'  ,  'å' ,


'`' ,   'a' ,  'c' ,  'ë',  'd' ,   'ì',   

'e' ,  'û' ,  'í' ,  'f' ,  'î' ,  'g' ,  'ñ' ,  'h' ,  'j' ,  'ú' ,  'k' ,

'Ô' ,  'Û' ,  'Ú' ,  'à' ,  'Þ' , 'Q­' ,  'º$' ,  'Ì' ,  'Ð' ,  'Õ' ,  'l' ,  'Îm' ,   '¸' ,   '„' ,  'ˆ' ,  'œ' ,  'Å' ,


'Am¡' ,  'Am{' ,  'Am|' ,  'Am' ,  'A' ,  'B©' ,  'B' , 'C' , 'D',   'E{',  'E' ,  'F' ,

'm°' ,    'm{' ,    'm|' ,    '{' ,   '|' ,  'm¡' ,   'm¢' ,   '¡' ,   '¢' , 

'm' ,    'r' ,   's' ,  't' ,    'w' ,  'þ' ,  'y' ,   '§' ,  '±',  '•' ,  '¥' ,  '²' , 

'Ñ' ,  '«' ,  'é' ,  'ê' ,  '&'    //,  '$' ,  '>' ,  'µ'  
 )

var array_two = new Array(  '©' ,  '©ं' ,  '{©' ,  'o' ,  'o' , 

"क",  'क्‌' , "ख",   'ख्‌' ,  "ग" ,  'ग्' ,  'घ' ,  

'च',  'च्‌',  'छ' ,  'ज़' ,  'ज' ,  'ज़्‌' ,  'ज्‌' ,  'झ' ,

"ट",  "ठ",   'ड़' ,  "ड",   'ढ़' ,  'ढ' , "ण" , 'ण्' ,

"थ",  'थ्' ,  "त",  'त्' ,  "ध", 'ध्' ,  "द",  "न" ,  'न्' ,

"फ", 'फ्‌' ,  "प", 'प्‌' ,  "भ",  'भ्' ,  "ब",  'ब्‌' ,  "म" ,   'म्' ,


"य",   "र",   "ल",  'ल्‌' ,   "व",   'व्‌' ,  

"श",  'श्' ,  'श्' ,  'ष' ,   'ष्‌' ,  "स",  'स्', "ह",  'क्ष' ,  'क्ष्' ,  'ज्ञ' ,

'द्द',  'द्व' , 'द्य' ,  'प्र',  'न्न' ,  'ट्र' , 'क्त' ,  'त्र' ,  'द्र',  'द्ध' ,  'श्र' ,  'त्त' ,  'क्क' ,  'ल्ल' ,  'ह्व' ,  'श्व' ,  'ट्ट' ,


'औ' ,  'ओ' , 'ओं' ,  'आ' ,  'अ' ,  'ई' ,  'इ' ,   'उ' ,  'ऊ' ,  'ऐ' ,  'ए' ,  'ऋ' ,

'ॉ' , "ो",  "ों",  "े",  "ें",  "ौ",  "ौं",   "ै",  'ैं' ,  

"ा",  "ी",  "ी",  "ीं",  "ु",  'ु' ,  "ू",  'ं' ,  'ँ' ,  'ः' ,  'ृ' , '्‌' ,  

'दृ' ,  '्र' ,  'रु' ,  'रू' ,  '।'    // ,  ''  ,  '' ,  ''  
 )

var array_one_length = array_one.length ;
var array_two_length = array_two.length ;


var modified_substring = document.getElementById("unicode_text").value  ;


//****************************************************************************************
//  Break the long text into small bunches of max. max_text_size  characters each.
//****************************************************************************************
    var text_size = document.getElementById("unicode_text").value.length ;

    var processed_text = '' ;  //blank

    var sthiti1 = 0 ;  var sthiti2 = 0 ;  var chale_chalo = 1 ;
 
    var max_text_size = 6000;

    while ( chale_chalo == 1 ) 
    {
     sthiti1 = sthiti2 ;

     if ( sthiti2 < ( text_size - max_text_size ) )  
     { 
      sthiti2 +=  max_text_size ;
      while (document.getElementById("unicode_text").value.charAt ( sthiti2 ) != ' ') {sthiti2--;}
     } 
     else  { sthiti2 = text_size  ;  chale_chalo = 0 }

      modified_substring = document.getElementById("unicode_text").value.substring ( sthiti1, sthiti2 )  ;

      Replace_Symbols( ) ;

      var processed_text = processed_text + modified_substring ;

      document.getElementById("legacy_text").value = processed_text  ;

    }
  	
	
	
 //--------------------------------------------------

 function Replace_Symbols( )
    {	
	// code for replacing "'िं'" (chhotee ee kii maatraa + anuswaar) with "q" and correcting its position too.
    modified_substring = '  ' + modified_substring  ; // add two spaces to avoid error while searching left    
        var position_of_f = modified_substring.indexOf( 'िं' )  ;
         while ( position_of_f != -1 )  //while-02
           {
		   modified_substring = modified_substring.replace( 'िं' , 'q' ) ;
            var character_left_to_f = modified_substring.charAt( position_of_f - 1 )  ;
            modified_substring = modified_substring.replace( character_left_to_f + "q" ,  "q" + character_left_to_f )  ;

            position_of_f = position_of_f - 1  ;

            while (( modified_substring.charAt( position_of_f - 1 ) == "्" )  &  ( position_of_f != 0  ) )
               {
                var string_to_be_replaced = modified_substring.charAt( position_of_f - 2 ) + "्"  ;
                  modified_substring = modified_substring.replace( string_to_be_replaced + "q", "q" + string_to_be_replaced ) ;

                position_of_f = position_of_f - 2  ;
               }
            position_of_f = modified_substring.search( /िं/ , position_of_f + 1 ) ; // search for f ahead of the current position.

           } // end of while-02 loop
	
//----------------------	
	
// code for replacing "ि" (chhotee ee kii maatraa) with "o" and correcting its position too.
        
        var position_of_f = modified_substring.indexOf( "ि" )  ;
         while ( position_of_f != -1 )  //while-02
           {
            var character_left_to_f = modified_substring.charAt( position_of_f - 1 )  ;
            modified_substring = modified_substring.replace( character_left_to_f + "ि" ,  "o" + character_left_to_f )  ;

            position_of_f = position_of_f - 1  ;

            while (( modified_substring.charAt( position_of_f - 1 ) == "्" )  &  ( position_of_f != 0  ) )
               {
                var string_to_be_replaced = modified_substring.charAt( position_of_f - 2 ) + "्"  ;
                  modified_substring = modified_substring.replace( string_to_be_replaced + "o", "o" + string_to_be_replaced ) ;

                position_of_f = position_of_f - 2  ;
               }
            position_of_f = modified_substring.search( /ि/ , position_of_f + 1 ) ; // search for f ahead of the current position.

           } // end of while-02 loop
 
//************************************************************     
        // Eliminating "र्" and putting  "©"   at proper position for this.

       set_of_matras = "ािीुूृेैोौं:ँॅ" 

modified_substring += '  '    ;  // add two spaces after the string to avoid UNDEFINED char in the following code.

       var position_of_half_R = modified_substring.indexOf( "र्" ) ;
        while ( position_of_half_R > 0  )  // while-04
           {
            // "र्"  is two bytes long
			if ( modified_substring.charAt( position_of_half_R + 3 ) != '्' )   var probable_position_of_Z = position_of_half_R + 2     
        else  var probable_position_of_Z = position_of_half_R + 4 ; 

            var character_right_to_probable_position_of_Z = modified_substring.charAt( probable_position_of_Z + 1 )

            // trying to find non-maatra position right to probable_position_of_Z .

            while ( set_of_matras.indexOf( character_right_to_probable_position_of_Z ) != -1 )  
               {
                probable_position_of_Z = probable_position_of_Z + 1 ;
                character_right_to_probable_position_of_Z = modified_substring.charAt( probable_position_of_Z + 1 ) ;
               } // end of while-05

            string_to_be_replaced = modified_substring.substr ( position_of_half_R + 2 , ( probable_position_of_Z - position_of_half_R - 1 ))  ;
            modified_substring = modified_substring.replace( "र्" + string_to_be_replaced  ,  string_to_be_replaced + "©" ) ;
            position_of_half_R = modified_substring.indexOf( "र्" ) ;
           } // end of while-04


        modified_substring = modified_substring.substr ( 0 , modified_substring.length - 2 )  ;
	
	
// ------------------------------------------	
	
	
	
//Now substitute array_one elements in place of corresponding array_two elements

     if ( modified_substring != "" )  // if string to be converted is non-blank then no need of any processing.
        {
         for (input_symbol_idx = array_two_length - 1 ;   input_symbol_idx > 0 ;    input_symbol_idx-- )
            {
             indx = 0  ;  // index of the symbol being searched for replacement
             
             while (indx != -1 ) //whie-00
                {
                 modified_substring = modified_substring.replace( array_two[ input_symbol_idx ] , array_one[input_symbol_idx] )
                 indx = modified_substring.indexOf( array_two[input_symbol_idx] )

                } // end of while-00 loop
            } // end of for loop
			
		 
    }//end of IF  statement  meant to  supress processing of  blank  string.

    } // end of the function  Replace_Symbols

 } // end of legacy_to_unicode function

