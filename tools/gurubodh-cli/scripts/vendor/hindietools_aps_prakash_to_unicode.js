function convert_to_unicode()
{

var array_one = new Array( "FË",
"eq","ef","ss","Rb","==","gâ","gbâ","bâ","sâ","tâ","&s",
"e&â","e@â","eWâ",      
"òeâ","eR","Dee@","X","x","Z","z","eA","ea","Ë","e|","eE","eR","eé",


"›eâ","kesâ","ke=â","kegâ","Ìkeâ","ÌHeâ","Ìpe","ÌKe","ÌÙe","Ìie","Heâ","heâ","Heä","heä",
"Ìkeä","ÌK",
"Ô","~","$e+",
"Í","Î",
"Œe","Œ","œe","œ","®","™","¤",

"°Ÿe","óŸe","šŸe","\"Ÿe","[Ÿe","{Ÿe", //"kebâ","›esâ",
"ß","$","«","›","¿","Ö","Ø","Ü","ã","ø","õ", 
"#","%","V","„","…","‰","‹","“","”","¢","£","¥","©","ª","§",
"°","º","»","À","Á","Â","Ã","Ä","Å","Æ","È","É","Ñ","Õ",

"æ","ñ","ò","ó","ô","ö","ù","ú","û","ÿ",

"Ì[","Ì{",

">","Ÿ","^","Ç","ü","ê",

"De", "F&","F","G","è","S","T",

"keä","keâ","¡","K","i","I","*",       
"Û","Ú","p","P","_",

"š","\"","[","{","C",
"l","L","o","O","v",
"h","H","y","Y","c",         // "heä","heâ",

"Ù","j","u","}","à","k","J","U","M","ç","ë","<","m","å","n","N",

"er","e","¦","¶","ƒ","†","‡","á","ì","í","î",
"g","Ï","t","Ò","=","ï","s","w","b","B","Š","d","]","Ì","@","Ó","Ê",
"Q","W",

"0","1","2","3","4","5","6","7","8","9",

"्ा","्ो","्ौ","अो","अा","आै","आे","ाो","ाॅ","ॅा","ाे","एे",
"ंु","ेे","अै","ाे","अे","ंा","अॅ","ाै","ैा","ंृ",
"ँा","ँू","ेा","ंे","ाें","ॅं","ंॅ"," ः","ंू","ेे")     // Remove typing mistakes in the original file

var array_two = new Array( "ईं",
"µ","µ","s","R","=","âg","âgb","âb","âs","ât","s&",
"eâ&","eâ@","eâW",

"क्त","ीं","ऑ","ें&","े&","ैं&","ै&","ीं&","ी&","ं&","र्µ","िं","िं","िं",
"क्र","के","कृ","कु","क़","फ़","ज़","ख़","य़","ग़","फ","फ","फ्","फ्",
"क़्","ख़्",
"ॐ","।","ऋ",
"्रू","्रु",
"स्त्र","स्त्र्","स्र","स्र्","रु","रू","रू",

"ष्ट्य","ट्ट्य","ट्य","ठ्य","ड्य","ढ्य",  //"कं","क्रे",
"श्र्","त्र्","ग्र्","व्र्","ज्र्","ह्न","प्र्","ह्र","झ्र्","प्र्","द्र",
"क्ष्","ज्ञ्","न्न्","ष्ट","ष्ठ","ष्ठ","ङ्घ","ङ्ख","ङ्ग","ह्य्","ह्व","ह्ल","द्म्","ट्ठ","श्च्",
"ष्ट","ड्ढ","ङ्क","ञ्ज्","ङ्ग","दृ","ञ्च्","व्न्","द्य्","द्भ","ङ्ख","द्व","ढ्ढ","श्व्",
"द्ध","ड्ड","त्त्","ट्ट","द्ब","द्द","हृ","ठ्ठ","द्ग","ह्म्",

"ड़","ढ़",
"्न","्य्","्र","्र","्र","्ल", 


"अ", "ई","इ","उ","ऌ","ए","ऊ",

"क्","क","ख्र्","ख्","ग्","घ्","ङ",
"च्","छ","ज्","झ्","ञ्",

"ट","ठ","ड","ढ","ण्", 
"त्","थ्","द","ध्","न्",
"प्","प्","ब्","भ्","म्",    // "फ्","फ",

"य्","र","ल्","ल","ळ्","व्","व्","ळ","श्","श्","श्","ष्","स्","ह्","ह","र्‍",

"ी","ा","ा","ा","ा","ा","ा","ा","ा","ा","ा",
"ु","ु","ू","ू","ृ","ॢ","े","ै","ं","ँ","ः","्","़","़","ॅ","ऽ","॰",
"ैं","ें",

"०","१","२","३","४","५","६","७","८","९",

"","े","ै","ओ","आ","औ","ओ","ो","ॉ","ॉ","ो","ऐ",
"ुं","े","अ‍ै","ो","अ‍े","ां","अ‍ॅ","ौ","ौ","ृं",
"ाँ","ूँ","ो","ें","ों","ँ","ँ"," :","ूं","े")     // Remove typing mistakes in the original file 

//**************************************************************************************
//
// Punctuation marks incorporated at the end
//******************************************************
//  Special glyphs
//******************************************************
//  "X",  "x", "Z",  "z", "eA", "ea", "Ë",  
//  "र्ें", "र्े", "र्ैं", "र्ै",  "र्ीं", "र्ी",  "र्ं",   
//  
//  "e\\", "e|", "eE", "eR", "eé",
//  "र्िं", "र्ि",  "िं",  "िं", "िं",
//******************************************************
//   ikAr and reph
//******************************************************
//   "ef","eq",
//   "ि","ि",
//
//   "&","N",
// "reph","reph (Marathi)",


//**************************************************************************************

    var array_one_length = array_one.length ;

    var modified_substring = document.getElementById("legacy_text").value  ;	
	
document.getElementById("unicode_text").value = "Conversion in progress.."  ;  

//****************************************************
//  Break the long text into small bunches of chunk_size  characters each.
//****************************************************
    var text_size = modified_substring.length ;

    var processed_text = '' ;  //blank

    var sthiti1 = 0 ;  var sthiti2 = 0 ;  var chale_chalo = 1 ;
 
    var chunk_size = 6000; // this charecter long text will be processed in one go.

    while ( chale_chalo == 1 ) 
    {
     sthiti1 = sthiti2 ;

     if ( sthiti2 < ( text_size - chunk_size ) )  
     { 
      sthiti2 +=  chunk_size ;
//      while (document.getElementById("legacy_text").value.charAt ( sthiti2 ) != ' ') {sthiti2--;} 
//This was making problem if there is no 'space' in the whole document.
     } 
     else  { sthiti2 = text_size  ;  chale_chalo = 0 }

  var modified_substring = document.getElementById("legacy_text").value.substring ( sthiti1, sthiti2 )  ;

  Replace_Symbols( ) ;

  var processed_text = processed_text + modified_substring ;
	  
document.getElementById("unicode_text").value = "Conversion in progress.." + '\n\n' + 'Conversion of ' + sthiti2 + ' charecters out of ' + text_size + ' completed.' ; 

    }
  
document.getElementById("unicode_text").value = processed_text  ;  


// --------------------------------------------------


function Replace_Symbols( )

{

//substitute array_two elements in place of corresponding array_one elements

if ( modified_substring != "" )  // if stringto be converted is non-blank then no need of any processing.
{
for ( input_symbol_idx = 0;   input_symbol_idx < array_one_length;    input_symbol_idx++ )

{ 

//  alert(" modified substring = "+modified_substring)

//***********************************************************
// if (input_symbol_idx==106) 
//  { alert(" input_symbol_idx = "+input_symbol_idx);
//    alert(" input_symbol_idx = "+input_symbol_idx)
//; alert(" character =" + modified_substring.CharCodeAt(input_symbol_idx))
//     alert(" character = "+modified_string.fromCharCode(input_symbol_idx)) 
//   }
// if (input_symbol_idx == 107) 
//   { alert(" input_symbol_idx = "+input_symbol_idx);
//    alert(" character = ",+string.fromCharCode(input_symbol_idx)) 
//   }
//***********************************************************
idx = 0  ;  // index of the symbol being searched for replacement

while (idx != -1 ) //while-00
{

modified_substring = modified_substring.replace( array_one[ input_symbol_idx ] , array_two[input_symbol_idx] )
idx = modified_substring.indexOf( array_one[input_symbol_idx] )

} // end of while-00 loop
// alert(" end of while loop")
} // end of for loop
// alert(" end of for loop")

// alert(" modified substring2 = "+modified_substring)
//*******************************************************

var position_of_i = modified_substring.indexOf( "µ" )

while ( position_of_i != -1 )  //while-02
{
var charecter_next_to_i = modified_substring.charAt( position_of_i + 1 )
var charecter_to_be_replaced = "µ" + charecter_next_to_i
modified_substring = modified_substring.replace( charecter_to_be_replaced , charecter_next_to_i + "ि" ) 
position_of_i = modified_substring.search( /µ/ , position_of_i + 1 ) // search for i ahead of the current position.

} // end of while-02 loop

//**********************************************************************************
// End of Code for Replacing four Special glyphs
//**********************************************************************************

// following loop to eliminate 'chhotee ee kee maatraa' on half-letters as a result of above transformation.

var position_of_wrong_ee = modified_substring.indexOf( "ि्" ) 

while ( position_of_wrong_ee != -1 )  //while-03

{
var consonent_next_to_wrong_ee = modified_substring.charAt( position_of_wrong_ee + 2 )
var charecter_to_be_replaced = "ि्" + consonent_next_to_wrong_ee 
modified_substring = modified_substring.replace( charecter_to_be_replaced , "्" + consonent_next_to_wrong_ee + "ि" ) 
position_of_wrong_ee = modified_substring.search( /ि्/ , position_of_wrong_ee + 2 ) // search for 'wrong ee' ahead of the current position. 

} // end of while-03 loop

// following loop to eliminate 'chhotee ee kee maatraa' on half-letters as a result of above transformation.

var position_of_wrong_ee = modified_substring.indexOf( "िं्" ) 

while ( position_of_wrong_ee != -1 )  //while-03

{
var consonent_next_to_wrong_ee = modified_substring.charAt( position_of_wrong_ee + 3 )
var charecter_to_be_replaced = "िं्" + consonent_next_to_wrong_ee 
modified_substring = modified_substring.replace( charecter_to_be_replaced , "्" + consonent_next_to_wrong_ee + "िं" ) 
position_of_wrong_ee = modified_substring.search( /िं्/ , position_of_wrong_ee + 3 ) // search for 'wrong ee' ahead of the current position. 

} // end of while-03 loop


// Eliminating reph "Ô" and putting 'half - r' at proper position for this.
set_of_matras = "ा ि ी ु ू ृ े ै ो ौ ं : ँ ॅ" 
//*****************************************************************
var position_of_R = modified_substring.indexOf( "&" )

// alert(" 1. modified_substring = "+modified_substring );
// alert(" 2. position_of_R = "+position_of_R )

while ( position_of_R > 0 )  // while-04
{
probable_position_of_half_r = position_of_R - 1 ;

 //alert(" 3. probable_position_of_half_r = "+probable_position_of_half_r );

var character_at_probable_position_of_half_r = modified_substring.charAt( probable_position_of_half_r )

 //alert(" 4. character_at_probable_position_of_half_r = "+character_at_probable_position_of_half_r );

//************************************************************
// trying to find non-maatra position left to current O (ie, half -r).
//************************************************************

while ( set_of_matras.match( character_at_probable_position_of_half_r ) != null )  // while-05
// some vowel maatraa or anusvaar found, move to previous character
   {   probable_position_of_half_r = probable_position_of_half_r - 1 ;
       character_at_probable_position_of_half_r = modified_substring.charAt( probable_position_of_half_r ) ;
   
     //alert(" 5. probable_position_of_half_r = "+probable_position_of_half_r );
     //alert(" 6. character_at_probable_position_of_half_r = "+character_at_probable_position_of_half_r );
   } // end of while-05

//************************************************************
// check if the previous character to the present character is a halant
//************************************************************
   var previous_to_position_of_half_r = probable_position_of_half_r - 1 ;
 //alert(" 7. previous_to_position_of_half_r = "+previous_to_position_of_half_r );

   if (previous_to_position_of_half_r > 0)  // if-03
   {  var character_previous_to_position_of_half_r = modified_substring.charAt( previous_to_position_of_half_r )
    //alert(" 8. character_previous_to_position_of_half_r = "+character_previous_to_position_of_half_r );

      while ("्".match( character_previous_to_position_of_half_r ) != null ) // while-06
//    halant found, move to previous character
      {  probable_position_of_half_r = previous_to_position_of_half_r - 1 ;
         character_at_probable_position_of_half_r = modified_substring.charAt( probable_position_of_half_r ) ;

       //alert(" 9. probable_position_of_half_r = "+probable_position_of_half_r );
       //alert("10. character_at_probable_position_of_half_r = "+character_at_probable_position_of_half_r );
       
         previous_to_position_of_half_r = probable_position_of_half_r - 1 ;
         character_previous_to_position_of_half_r = modified_substring.charAt( previous_to_position_of_half_r )

       //alert("11. previous_to_position_of_half_r = "+previous_to_position_of_half_r );
       //alert("12. character_previous_to_position_of_half_r = "+character_previous_to_position_of_half_r );
      } // end of while-06
   } // end of if-03

//************************************************************

character_to_be_replaced = modified_substring.substr ( probable_position_of_half_r , ( position_of_R - probable_position_of_half_r ) ) ;
new_replacement_string = "र्" + character_to_be_replaced ; 
character_to_be_replaced = character_to_be_replaced + "&" ;
modified_substring = modified_substring.replace( character_to_be_replaced , new_replacement_string ) ;
position_of_R = modified_substring.indexOf( "&" ) ;

 //alert("13. character_to_be_replaced = "+character_to_be_replaced );
 //alert("14. modified_substring = "+modified_substring );

} // end of while-04

} // end of IF  statement  meant to  supress processing of  blank  string.


} // end of the function  Replace_Symbols

} // end of convert_to_unicode function


//*******************************************************************************


function convert_to_Prakash()
{
var array_one = new Array("“", "”", "\"", // "् ", "्,", "्;", "्।", //"र्य","र्ह",
// "क़","ख़","ग़","ज़","ड़","ढ़","फ़",  // two-byte varnas                      //07
"फ्र","ऑ","क्त","क्र","के","कृ","कु",
"क़्","ख़्","क़","फ़","ज़","ख़","य़","ग़", //"फ","फ","फ्","फ्",           //16

"त्र","श्र","स्र","ग्र","व्र","ज्र","प्र","ह्र","झ्र",
"त्र्","श्र्","स्र्","ग्र्","व्र्","ज्र्","प्र्","झ्र्",
"द्र",
"घ्र","ध्र","ब्र","भ्र","म्र",
"छ्र","ट्र","ठ्र","ड्र","ढ्र",
"्रू","्रु","रु","रू",

//"घ्र","ध्र","ब्र","भ्र","म्र",
//"ष्ट्र", "रु","रू",

"ॐ","।", "\|", "ऋ",                    						    //03
"स्त्र","स्त्र्",                  				    //07

"क्षि","त्रि","ज्ञि","श्रि",                     					    //04
"ह्न",                    	    //13
//"्रू","्रु","रु","रू",

"क्ष्","क्ष","ज्ञ्","ज्ञ","न्न्","न्न","ष्ठ","ष्ठ","ङ्घ","ङ्ख","ङ्ग","ह्य्","ह्य","ह्व","ह्ल","द्म्","द्म","ट्ठ", //"श्च्","श्च",     //17
"ड्ढ","ङ्क","ञ्ज्","ञ्ज","ङ्ग","दृ",
"ञ्च्","व्न्","द्य्","ञ्च","व्न","द्य","द्भ","ङ्ख","द्व","ढ्ढ","श्व्","श्व",              //15 "ष्ट्र","ष्ट",
"द्ध","ड्ड","त्त्","त्त","ट्ट","द्ब","द्द","हृ","ठ्ठ","द्ग","ह्म्","ह्म",                                //10

"ड़","ढ़",                                                           //02
"ष्ट्य","ट्ट्य","ट्य","ठ्य","ड्य","ढ्य",  //"कं","क्रे",

"्र",                                         //07
//"्न","्ल",                                                    //03

"क्","क","ख्","ख","ग्","ग","घ्","घ","ङ",                                    //09 
"च्","च","छ","ज़्","ज़","ज्","ज","झ्","झ","ञ्","ञ",                             //11
"ट","ठ","ड","ढ","ण्","ण",                                              //06
"त्","त","थ्","थ","द","ध्","ध","न्","न",                                    //09
"प्","प","फ्","फ","ब्","ब","भ्","भ","म्","म",                                //10

"शृ","य्","य","र","ल्","ल","ळ्","ळ","व्","व","श्","श","ष्","ष","स्","स","ह्","ह",        //18 // "श्","श्",
"्य्",//"र्‍",
"औ","ओ","ऑ","आ","अ","ई","इ","उ","ऊ","ऋ","ऌ","ऐ","ए",                     //13

"ौ","ो","ॉ","ा","ी","ु","ू","ृ","ॢ","े","ै","ँ","ं","ः","्","ॅ","ऽ","़","॰",       //18

"०","१","२","३","४","५","६","७","८","९"   )

var array_two = new Array("‘", "’", "'",  // "d ", "d\,", "d\;", "d~", //"NÙe","Nn",
// "क़","ख़","ग़","ज़","ड़","ढ़","फ़",  //one-byte varnas
"Øeâ","Dee@","òeâ","›eâ","kesâ","ke=â","kegâ",
"Ìkeä","ÌK","Ìkeâ","ÌHeâ","Ìpe","ÌKe","ÌÙe","Ìie", //"Heâ","heâ","Heä","heä",


"$e","ße","œe","«e","›e","¿e","Øe","Ü","ãe",
"$","ß","œ","«","›","¿","Ø","ã",
"õ",
"IeÇ","OeÇ","yeÇ","YeÇ","ceÇ",
"Ú^","š^","\"^","[^","{^",
"Í","Î","®","™", 


"Ô","~", "~", "$e+",
"Œe","Œ",

"ef#e","ef$e","ef%e","efße",
"Ö",
//"Í","Î","®","™", 

"#","#e","%","%e","V","Ve","…","‰","‹","“","”","¢","¢e","£","¥","©","©e","ª", //"§","§e",
"º","¿","À","Àe","Á","Â",
"Ã","Ä","Å","Ãe","Äe","Åe","Æ","È","É","Ñ","Õ","Õe",  //"°^","°",
"æ","ñ","ò","òe","ó","ô","ö","ù","ú","û","ÿ","ÿe",

"Ì[","Ì{",
"°Ÿe","óŸe","šŸe","\"Ÿe","[Ÿe","{Ÿe", //"kebâ","›esâ",

"Ç",
//">","ê",

"keä","keâ","K","Ke","i","ie","I","Ie","*",     
"Û","Ûe","Ú","[p","[pe","p","pe","P","Pe","_","_e",
"š","\"","[","{","C","Ce",
"l","le","L","Le","o","O","Oe","v","ve",
"h","he","heä","heâ","y","ye","Y","Ye","c","ce",

"ëe=","Ù","Ùe","j","u","}","à","U","k","ke","M","Me","<","<e","m","me","å","n",  // "ç","ë",
"Ÿ",//"N",
"Deew","Dees","Dee@","Dee","De","F&","F","G","T","$e+","è","Ss","S",

"ew","es","e@","e","er","g","t","=","ï","s","w","B","b","Š","d","@","Ó","Ì","Ê",

"0","1","2","3","4","5","6","7","8","9"    )

//************************************************************
//Put "Enter chunk size:" line before "<textarea name= ..." if required to be used.    
//************************************************************
//Enter chunk size: <input type="text" name="chunksize" value="6000" size="7" maxsize="7" style="text-align:right"><br/><br/>
//************************************************************
// The following two characters are to be replaced through proper checking of locations:
//******************************************************
//   ikAr and reph
//******************************************************
//   "ef","eq",
//   "ि","ि",
//
//   "&","N",
// "reph","reph (Marathi)",
//**************************************************************************************

var array_one_length = array_one.length ;

    var modified_substring = document.getElementById("unicode_text").value + " " ;	// an space added to help recognise halant at the end of file
	
document.getElementById("legacy_text").value = "Conversion in progress.."  ;  

//****************************************************
//  Break the long text into small bunches of chunk_size  characters each.
//****************************************************
    var text_size = modified_substring.length ;

    var processed_text = '' ;  //blank

    var sthiti1 = 0 ;  var sthiti2 = 0 ;  var chale_chalo = 1 ;
 
    var chunk_size = 6000; // this charecter long text will be processed in one go.

    while ( chale_chalo == 1 ) 
    {
     sthiti1 = sthiti2 ;

     if ( sthiti2 < ( text_size - chunk_size ) )  
     { 
      sthiti2 +=  chunk_size ;
//      while (document.getElementById("unicode_text").value.charAt ( sthiti2 ) != ' ') {sthiti2--;} 
//This was making problem if there is no 'space' in the whole document.
     } 
     else  { sthiti2 = text_size  ;  chale_chalo = 0 }

  var modified_substring = document.getElementById("unicode_text").value.substring ( sthiti1, sthiti2 )  ;

  
  Replace_Symbols( ) ;

  var processed_text = processed_text + modified_substring ;
	  
document.getElementById("legacy_text").value = "Conversion in progress.." + '\n\n' + 'Conversion of ' + sthiti2 + ' charecters out of ' + text_size + ' completed.' ; 

    }
  
document.getElementById("legacy_text").value = processed_text  ;  


// --------------------------------------------------


function Replace_Symbols( )
   {
   
    // if string to be converted is non-blank then no need of any processing.
    if (modified_substring != "" )  
       {

modified_substring = modified_substring.replace ( /\)/g , " \)" ) ;
	   
modified_substring = modified_substring.replace ( /द्र्/g , "õd" ) ;
	   
  
// Halanta after which there is no constant but space, hypen, comma or full-stop etc

modified_substring = modified_substring.replace ( /्([ \,\;\.।\n\-\:])/g , "d$1" ) ;
// modified_substring = modified_substring.replace ( /[्]([^कखगघचछजझटठडड़ढढ़णतथदधनपफबभमयरलळवशषसहक्षज्ञ])/g , "d$1" ) ;	   
	   
// maraathi style reph 
modified_substring = modified_substring.replace ( /ऱ्/g , "N" )  ; 
	   
// maraathi style reph ; there is a hidden ZWJ after र् 
modified_substring = modified_substring.replace ( /र्‍/g , "N" )  ; 	   
	   
modified_substring = modified_substring.replace ( /त्र्य/g , "$य" )  ; 
modified_substring = modified_substring.replace ( /श्र्य/g , "ßय" )  ; 

// first replace the two-byte nukta_varNa with corresponding one-byte nukta varNas.

 modified_substring = modified_substring.replace ( /क़/g , "क़" )  ; 
 modified_substring = modified_substring.replace ( /ख़‌/g , "ख़" )  ;
 modified_substring = modified_substring.replace ( /ग़/g , "ग़" )  ;
 modified_substring = modified_substring.replace ( /ज़/g , "ज़" )  ;
 modified_substring = modified_substring.replace ( /ड़/g , "ड़" )  ;
 modified_substring = modified_substring.replace ( /ढ़/g , "ढ़" )  ;
// modified_substring = modified_substring.replace ( /ऩ/g , "ऩ" )  ;
 modified_substring = modified_substring.replace ( /फ़/g , "फ़" )  ;
// modified_substring = modified_substring.replace ( /य़/g , "य़" )  ;
// modified_substring = modified_substring.replace ( /ऱ/g , "ऱ" )  ;


// code for replacing "ि" (chhotee ee kii maatraa) with "ef"  and correcting its position too.
        
        var position_of_f = modified_substring.indexOf( "ि" )  ;
         while ( position_of_f != -1 )  //while-02
           {
            var character_left_to_f = modified_substring.charAt( position_of_f - 1 )  ;
            modified_substring = modified_substring.replace( character_left_to_f + "ि" ,  "µ" + character_left_to_f )  ;

            position_of_f = position_of_f - 1  ;

            while (( modified_substring.charAt( position_of_f - 1 ) == "्" )  &  ( position_of_f != 0  ) )
               {
                var string_to_be_replaced = modified_substring.charAt( position_of_f - 2) + "्"  ;
                  modified_substring = modified_substring.replace( string_to_be_replaced + "µ", "µ" + string_to_be_replaced ) ;

                position_of_f = position_of_f - 2  ;
               }
            position_of_f = modified_substring.search( /ि/ , position_of_f + 1 ) ; // search for f ahead of the current position.

           } // end of while-02 loop
   //************************************************************     
   //     modified_substring = modified_substring.replace( /fर्/g , "£"  )  ;
   //************************************************************     
        // Eliminating "र्" and putting  Z  at proper position for this.

       set_of_matras = "ािीुूृेैोौंःँॅ" 

       modified_substring += '  '    ;  // add two spaces after the string to avoid UNDEFINED char in the following code.
 
//     modified_substring = modified_substring.replace ( /-/g , "¹" )  ; 
//     modified_substring = modified_substring.replace ( /श्र्/g , "E" )  ; 
       var space = " "
       var position_of_half_R = modified_substring.indexOf( "र्" ) ;

//************************************************************************************
   while ( position_of_half_R > 0  )  // while-03
   {
    // "र्"  is two bytes long
    var probable_position_of_Z = position_of_half_R + 2   ;  
    var character_at_probable_position_of_Z = modified_substring.charAt( probable_position_of_Z )

//  alert(" 3. probable_position_of_Z = "+probable_position_of_Z );
//  alert(" 4. character_at_probable_position_of_Z = "+character_at_probable_position_of_Z );

    // trying to find non-maatra position right to probable_position_of_Z .

    while( set_of_matras.match( character_at_probable_position_of_Z ) != null ) // while-04 
    {
     probable_position_of_Z = probable_position_of_Z + 1 ;
     character_at_probable_position_of_Z = modified_substring.charAt( probable_position_of_Z ) ;

//   alert(" 5. probable_position_of_Z = "+probable_position_of_Z );
//   alert(" 6. character_at_probable_position_of_Z = "+character_at_probable_position_of_Z );
    } // end of while-04
//************************************************************
// check if the next character is a halant
//************************************************************
    var right_to_position_of_Z = probable_position_of_Z + 1 ;
//  alert(" 7. right_to_position_of_Z = "+right_to_position_of_Z );

    if (right_to_position_of_Z > 0)  // if-03
    { var character_right_to_position_of_Z = modified_substring.charAt( right_to_position_of_Z )
//    alert(" 8. character_right_to_position_of_Z = "+character_right_to_position_of_Z );

      while ("्".match( character_right_to_position_of_Z ) != null ) // while-05
      {  
//       halant found, move to next character
         probable_position_of_Z = right_to_position_of_Z + 1 ;
         character_at_probable_position_of_Z = modified_substring.charAt( probable_position_of_Z ) ;

//       alert(" 9. probable_position_of_Z = "+probable_position_of_Z );
//       alert("10. character_at_probable_position_of_Z = "+character_at_probable_position_of_Z );
       
         right_to_position_of_Z = probable_position_of_Z + 1 ;
         character_right_to_position_of_Z = modified_substring.charAt( right_to_position_of_Z )

//       alert("11. right_to_position_of_Z = "+right_to_position_of_Z );
//       alert("12. character_right_to_position_of_Z = "+character_right_to_position_of_Z );
      } // end of while-05
   } // end of if-03
//************************************************************

       string_to_be_replaced = modified_substring.substr ( position_of_half_R + 2,(probable_position_of_Z - position_of_half_R)-1) ;
//************************************************************
//     check if character_right_to_position_of_Z is a space
//       if (space.match(character_right_to_position_of_Z) != null) 
//       {
//          string_to_be_replaced = string_to_be_replaced.substr(0,string_to_be_replaced.length - 1)
//        alert("13. string_to_be_replaced = "+string_to_be_replaced );
//        alert("14. string_to_be_replaced.length ="+string_to_be_replaced.length);
//       }
       modified_substring = modified_substring.replace( "र्" + string_to_be_replaced, string_to_be_replaced + "&" ) ;

//     alert("15. string_to_be_replaced = "+string_to_be_replaced );
//     alert("16. modified_substring = "+modified_substring );
       position_of_half_R = modified_substring.indexOf( "र्" ) ;
//      alert("17. position_of_half_R = "+position_of_half_R )

   } // end of while-03
//***********************************************************

modified_substring = modified_substring.substr ( 0 , modified_substring.length - 2 )  ;

        //substitute array_two elements in place of corresponding array_one elements

        for( input_symbol_idx = 0; input_symbol_idx < array_one_length; input_symbol_idx++ )
           {
            idx = 0  ;  // index of the symbol being searched for replacement

            while (idx != -1 ) //whie-00
               {
                modified_substring = modified_substring.replace( array_one[ input_symbol_idx ] , array_two[input_symbol_idx] )
                idx = modified_substring.indexOf( array_one[input_symbol_idx] )
               } // end of while-00 loop
           } // end of for loop

        } // end of IF  statement  meant to  supress processing of  blank  string.

     modified_substring = modified_substring.replace ( /µ/g , "ef" ) 
     modified_substring = modified_substring.replace ( /d &/g , "d&" ) 
     modified_substring = modified_substring.replace ( /žNÙe/g , "NÙe" ) 
     modified_substring = modified_substring.replace ( /ž&n/g , "Nn" ) 
  //   modified_substring = modified_substring.replace ( /&Ùe/g , "NÙe" ) 
  //   modified_substring = modified_substring.replace ( /n&/g , "Nn" ) 
     modified_substring = modified_substring.replace ( /&er/g , "er&" ) 
     modified_substring = modified_substring.replace ( /&e/g , "e&" ) 
     modified_substring = modified_substring.replace ( /eâ&/g , "e&â" ) 
     modified_substring = modified_substring.replace ( /^g/g , "Î" ) 
     modified_substring = modified_substring.replace ( /^t/g , "Í" ) 
     modified_substring = modified_substring.replace ( /&sb/g , "X" )
     modified_substring = modified_substring.replace ( /&wb/g , "Z" )
     modified_substring = modified_substring.replace ( /&â/g , "â&" )
     modified_substring = modified_substring.replace ( /e&f/g , "&ef" )

     modified_substring = modified_substring.replace ( /&b/g , "Ë" )
	 
     modified_substring = modified_substring.replace ( /âd([^ \,\;\.।\n\-\:])/g , "ä$1" )
	 
     modified_substring = modified_substring.replace ( /wb/g , "Q" )
     modified_substring = modified_substring.replace ( /sb/g , "W" )
     modified_substring = modified_substring.replace ( /rb/g , "R" )


//following to take care of pf, ka, ha etc having 'bakuli'.
 modified_substring = modified_substring.replace( /eâ([\&g])/g , "e$1â" ) ;

// following for converting ॊ
 modified_substring = modified_substring.replace( /ॊ/g , "es" ) ;

// remove the space put before closing bracket ')'
 modified_substring = modified_substring.replace ( / \)/g , "\)" ) ;
 
     } // end of the function  Replace_Symbols( )

  } // end of convert_to_Prakash function

