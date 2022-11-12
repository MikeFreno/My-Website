function showReplyBox(vars){
    var reply_box = document.getElementById(vars);
    if ( reply_box.style.display == 'none' ){
    //If the div is hidden, show it
    reply_box.style.display = 'block';
    //change button to gold
    document.getElementById(`reply_button${vars}`).style.color="#F2A900"
  } else {
    //If the div is shown, hide it
    reply_box.style.display = 'none';
    //change button to white
    document.getElementById(`reply_button${vars}`).style.color="white"
  }
}