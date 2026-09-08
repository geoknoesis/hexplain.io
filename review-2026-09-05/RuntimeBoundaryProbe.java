import io.hexplain.rt.ByteReader;
public class RuntimeBoundaryProbe {
 public static void main(String[] args) {
  var negative=new ByteReader(new byte[]{1,2},0);
  negative.region(-1,()->0);
  if(negative.position()!=-1)throw new AssertionError();
  System.out.println("CONFIRMED: negative region leaves cursor at -1");
  var overflow=new ByteReader(new byte[]{1,2},1);
  overflow.region(Integer.MAX_VALUE,()->0);
  if(overflow.position()!=Integer.MIN_VALUE)throw new AssertionError();
  System.out.println("CONFIRMED: region addition overflows to Integer.MIN_VALUE");
  var alignment=new ByteReader(new byte[10],1);
  alignment.align(4294967298L);
  if(alignment.position()!=2)throw new AssertionError();
  System.out.println("CONFIRMED: alignment 4294967298 narrows to 2");
 }
}
